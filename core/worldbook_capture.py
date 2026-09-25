"""Asynchronous, low-risk capture of stable worldbook additions from played turns."""

from __future__ import annotations

import json
import threading
import uuid
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import yaml

from core.ai_engine import robust_json_parse
from core.auto_worldbook import select_capture_worldbook
from core.worldbook import normalize_entry, normalize_tags, normalize_worldbook, save_worldbook_atomic, worldbook_revision, WorldbookRevisionConflict
from core.capture_source import source_is_current
from core.world_rule_commands import capture_instruction, world_rule_command_mode
from core.world_change_events import confirmed_world_changes
from utils.sys_logger import get_logger


log = get_logger()
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


CAPTURE_PROMPT = """你是世界书设定捕获器。阅读一个已经完成的故事回合，只识别值得长期保留的稳定世界设定。

变化可来自任何机制，不依赖固定命令词。先核对世界变化信号与正文：尝试、愿望、对白、谎言、传闻、梦境或失败不等于确认事实。
区分客观现实、制度、群体认知、记忆档案与局部例外；大家相信某事不代表它客观为真。保留实际适用范围和持续条件，不把局部或有期限的规则扩写为全局永久规则。
暂停、恢复、到期必须定位既有目标。本阶段仅支持条目 add/update/retire 提案；无法用这些操作准确表达、缺少历史原文或属于公理/概述的变化不要猜写或转成新增。尤其不得凭空重建所谓原始版本。

世界书不是剧情摘抄簿。一次出现、能在未来派上用场或具有特殊功能，不等于值得写入世界观。
不要捕获：一次性动作、当前伤势、临时地点状态、角色计划、幕后行动、普通剧情摘要、单件特殊道具、角色或暗流实体资料、实体制造的陷阱与线索。这些分别属于正文、状态、角色卡、实体库或因果账本。
可以捕获：预计长期约束许多场景的法律、制度、社会习俗、自然规律、通用技术/魔法规则。稳定地点、独特物品或人物传闻只能作为待确认候选，不能自动升格为世界事实。
允许识别三种操作：add 新增世界常识、update 修改已有世界常识、retire 废止已有世界常识。update/retire 必须引用当前世界书中准确的 target_entry_id；系统会强制等待玩家确认，不能直接改写既有事实。不要创造绝对规则。与现有条目重复且没有变化时不要输出。
scope 必须从以下枚举选择：world_rule、social_system、natural_law、technology_magic_rule、stable_location、unique_item、character_entity、event_detail。
confidence 必须为 high、medium 或 low。只有正文明确建立、并且可跨多个场景持续约束世界时才可写 high；由单回合细节推测出的内容不得写 high。

严格输出 JSON：
{
  "candidates": [
    {"operation":"add|update|retire","target_entry_id":"仅修改/废止时填写","name":"条目名","content":"稳定设定","keys":"可选明确触发词","tags":["AI推断"],"risk":"low|high","scope":"上述枚举","confidence":"high|medium|low","reason":"为何属于长期世界设定"}
  ]
}
"""

AUTO_CAPTURE_SCOPES = {
    "world_rule",
    "social_system",
    "natural_law",
    "technology_magic_rule",
}
NEVER_CAPTURE_SCOPES = {"event_detail"}

def capture_requested(settlement: dict[str, Any] | None, player_action: Any = "") -> bool:
    """New evidence wins over legacy flags/aliases, including an explicit empty list."""
    if isinstance(settlement, dict) and "world_change_events" in settlement:
        return bool(confirmed_world_changes(settlement))
    return (
        isinstance(settlement, dict) and settlement.get("worldbook_capture_needed") is True
    ) or bool(world_rule_command_mode(player_action))


def _path_lock(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


class WorldbookCaptureService:
    def __init__(self, ai_engine):
        self.ai_engine = ai_engine

    @staticmethod
    def first_active_worldbook(save_dir: str) -> Path | None:
        return select_capture_worldbook(save_dir)

    def schedule(self, save_dir: str, player_action: str, story_text: str, *, review_all: bool, world_change_events=None, source_turn=None) -> bool:
        if source_turn is not None and not source_is_current(save_dir, source_turn):
            log.info("世界书捕获未启动：源回合未保存或已失效")
            return False
        path = select_capture_worldbook(save_dir, create_fallback=True)
        if not path or not self.ai_engine or not story_text.strip():
            return False
        thread = threading.Thread(
            target=self._run_capture,
            args=(path, player_action, story_text),
            kwargs={"review_all": review_all, "world_change_events": world_change_events,
                    "source_turn": source_turn, "save_dir": save_dir,
                    "expected_revision": worldbook_revision(path.read_bytes())},
            name="worldbook-capture",
            daemon=True,
        )
        thread.start()
        return True

    def _run_capture(self, *args, **kwargs):
        try:
            result = self.capture(*args, **kwargs)
            if result.get("skipped"):
                log.info("世界书后台捕获跳过项: %s", result["skipped"])
            return result
        except Exception as exc:
            log.exception("世界书后台捕获失败，已保存正文不受影响: %s", exc)

    def capture(self, path: Path, player_action: str, story_text: str, *, review_all: bool, world_change_events=None,
                source_turn=None, save_dir=None, expected_revision=None) -> dict[str, Any]:
        if source_turn is not None and not source_is_current(save_dir, source_turn):
            return {"added": [], "pending": [], "skipped": ["源回合已失效"]}
        if world_change_events is not None:
            world_change_events = confirmed_world_changes({"world_change_events": world_change_events, "story_text": story_text})
            if not world_change_events:
                return {"added": [], "pending": [], "skipped": ["无有效世界变化证据"]}
            # Until revision/time semantics are implemented, these signals must
            # not silently become permanent auto-accepted additions.
            review_all = review_all or any(
                event["change_kind"] != "add" or event["time_hint"] != "persistent"
                or event["scope_hint"] == "individual_exception"
                for event in world_change_events
            )
        with _path_lock(path):
            try:
                original = path.read_bytes()
                revision = worldbook_revision(original)
                if expected_revision is not None and revision != expected_revision:
                    return {"added": [], "pending": [], "skipped": ["目标修订已变化"]}
                book = normalize_worldbook(yaml.safe_load(original.decode("utf-8")) or {})
            except (OSError, yaml.YAMLError) as exc:
                log.warning("世界书异步捕获无法读取目标: %s", exc)
                return {"added": [], "pending": [], "skipped": ["读取失败"]}

            command_mode = world_rule_command_mode(player_action)
            command_instruction = capture_instruction(player_action)
            command_section = (
                f"【本回合附加捕获规则】\n{command_instruction}\n" if command_instruction else ""
            )
            prompt = (
                f"【当前世界书】\n{json.dumps(book, ensure_ascii=False)}\n"
                f"【已校验世界变化信号】\n{json.dumps(world_change_events, ensure_ascii=False)}\n"
                f"{command_section}"
                f"【玩家行动】\n{player_action}\n【本回合正文】\n{story_text}"
            )
            raw, error = self.ai_engine.chat_json(CAPTURE_PROMPT, prompt, temp=0.3, trace_label="世界书异步捕获")
            if error or not raw:
                log.warning("世界书异步捕获失败，正文不受影响: %s", error or "空返回")
                return {"added": [], "pending": [], "skipped": [error or "空返回"]}
            try:
                payload = robust_json_parse(raw)
            except ValueError as exc:
                log.warning("世界书异步捕获JSON无效，正文不受影响: %s", exc)
                return {"added": [], "pending": [], "skipped": [str(exc)]}

            existing_names = {entry.get("name", "").casefold() for entry in book.get("entries", [])}
            existing_contents = {entry.get("content", "").strip() for entry in book.get("entries", [])}
            existing_by_id = {entry.get("id"): entry for entry in book.get("entries", []) if entry.get("id")}
            pending_operations = {
                (entry.get("pending_operation"), entry.get("replaces_entry_id"))
                for entry in book.get("entries", []) if entry.get("pending_operation")
            }
            added, pending, skipped = [], [], []
            for raw_candidate in payload.get("candidates", []) if isinstance(payload.get("candidates"), list) else []:
                if not isinstance(raw_candidate, dict):
                    continue
                tags = normalize_tags(raw_candidate.get("tags", []))
                operation = str(raw_candidate.get("operation", "add")).strip().lower() or "add"
                if command_mode == "restore" and operation not in {"update", "retire"}:
                    skipped.append(str(raw_candidate.get("name", "常识恢复不得新增条目")))
                    continue
                if command_mode == "change" and "常识改变" not in tags:
                    tags.append("常识改变")
                if command_mode == "restore" and "常识恢复" not in tags:
                    tags.append("常识恢复")
                scope = str(raw_candidate.get("scope", "")).strip()
                confidence = str(raw_candidate.get("confidence", "")).strip()
                if scope in NEVER_CAPTURE_SCOPES:
                    skipped.append(str(raw_candidate.get("name", "剧情细节")))
                    continue
                if operation in {"update", "retire"}:
                    target_id = str(raw_candidate.get("target_entry_id", "")).strip()
                    target = existing_by_id.get(target_id)
                    if not target or (operation, target_id) in pending_operations:
                        skipped.append(str(raw_candidate.get("name") or target_id or "无效变更"))
                        continue
                    proposal_tags = normalize_tags([*target.get("tags", []), *tags, "AI推断", "待确认"])
                    proposal = normalize_entry({
                        **target,
                        **(raw_candidate if operation == "update" else {}),
                        "id": "",
                        "name": str(raw_candidate.get("name") or target.get("name", "")).strip(),
                        "content": str(raw_candidate.get("content") or target.get("content", "")).strip(),
                        "keys": str(raw_candidate.get("keys") or target.get("keys", "")).strip(),
                        "tags": proposal_tags,
                        "is_active": False,
                        "pending_operation": operation,
                        "replaces_entry_id": target_id,
                        "proposal_reason": str(raw_candidate.get("reason", "")).strip(),
                    })
                    proposal["id"] = f"proposal_{uuid.uuid4().hex[:12]}"
                    book.setdefault("entries", []).append(proposal)
                    pending_operations.add((operation, target_id))
                    pending.append(proposal)
                    continue
                if operation != "add":
                    skipped.append(str(raw_candidate.get("name", "未知操作")))
                    continue
                high_risk = raw_candidate.get("risk") != "low" or "绝对规则" in tags
                safe_to_auto_add = scope in AUTO_CAPTURE_SCOPES and confidence == "high" and not high_risk
                if "AI推断" not in tags:
                    tags.append("AI推断")
                if review_all or not safe_to_auto_add:
                    tags.append("待确认")
                candidate = normalize_entry({**raw_candidate, "tags": tags})
                if not candidate["name"] or not candidate["content"]:
                    skipped.append("缺少名称或内容")
                    continue
                if candidate["name"].casefold() in existing_names or candidate["content"] in existing_contents:
                    skipped.append(candidate["name"])
                    continue
                book.setdefault("entries", []).append(candidate)
                existing_names.add(candidate["name"].casefold())
                existing_contents.add(candidate["content"])
                (pending if "待确认" in candidate["tags"] else added).append(candidate)

            if added or pending:
                # Share the story mutation gate only for the short commit, not
                # the model request. Undo/save and source checking cannot race.
                from core.session_manager import mutation_guard, save_identity
                gate = mutation_guard("story", save_identity(save_dir), blocking=True) if source_turn is not None else nullcontext()
                try:
                    with gate:
                        if source_turn is not None and not source_is_current(save_dir, source_turn):
                            log.info("世界书异步捕获弃用：源回合已撤回或替换")
                            return {"added": [], "pending": [], "skipped": ["源回合已失效"]}
                        save_worldbook_atomic(path, book, expected_revision=revision)
                except (WorldbookRevisionConflict, OSError) as exc:
                    log.warning("世界书异步捕获未写入: %s", exc)
                    return {"added": [], "pending": [], "skipped": [str(exc)]}
            log.info("世界书异步捕获完成: target=%s auto_added=%s pending=%s skipped=%s", path.name, [item["name"] for item in added], [item["name"] for item in pending], skipped)
            return {"added": added, "pending": pending, "skipped": skipped}
