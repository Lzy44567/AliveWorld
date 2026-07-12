"""Asynchronous, low-risk capture of stable worldbook additions from played turns."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import yaml

from core.ai_engine import robust_json_parse
from core.worldbook import normalize_entry, normalize_tags, normalize_worldbook, save_worldbook_atomic
from utils.sys_logger import get_logger


log = get_logger()
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


CAPTURE_PROMPT = """你是世界书设定捕获器。阅读一个已经完成的故事回合，只识别值得长期保留的稳定世界设定。

不要捕获：一次性动作、当前伤势、临时地点状态、角色计划、幕后行动、尚未证实的角色台词、普通剧情摘要。这些属于正文、状态、实体或因果账本。
可以捕获：新出现且预计长期成立的法律、制度、社会习俗、自然规律、技术/魔法规则、稳定地点背景。
只允许提出全新条目，不修改或删除已有条目，不创造绝对规则。与现有条目重复或冲突时不要输出。

严格输出 JSON：
{
  "candidates": [
    {"name":"条目名","content":"稳定设定","keys":"可选明确触发词","tags":["AI推断"],"risk":"low|high","reason":"为何属于长期世界设定"}
  ]
}
"""


def _path_lock(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


class WorldbookCaptureService:
    def __init__(self, ai_engine):
        self.ai_engine = ai_engine

    @staticmethod
    def first_active_worldbook(save_dir: str) -> Path | None:
        directory = Path(save_dir) / "worldbooks"
        for path in sorted(directory.glob("*.yml")) if directory.exists() else []:
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                if data.get("is_active", True):
                    return path
            except (OSError, yaml.YAMLError):
                continue
        return None

    def schedule(self, save_dir: str, player_action: str, story_text: str, *, review_all: bool) -> bool:
        path = self.first_active_worldbook(save_dir)
        if not path or not self.ai_engine or not story_text.strip():
            return False
        thread = threading.Thread(
            target=self.capture,
            args=(path, player_action, story_text),
            kwargs={"review_all": review_all},
            name="worldbook-capture",
            daemon=True,
        )
        thread.start()
        return True

    def capture(self, path: Path, player_action: str, story_text: str, *, review_all: bool) -> dict[str, Any]:
        with _path_lock(path):
            try:
                book = normalize_worldbook(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
            except (OSError, yaml.YAMLError) as exc:
                log.warning("世界书异步捕获无法读取目标: %s", exc)
                return {"added": [], "pending": [], "skipped": ["读取失败"]}

            prompt = (
                f"【当前世界书】\n{json.dumps(book, ensure_ascii=False)}\n"
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
            added, pending, skipped = [], [], []
            for raw_candidate in payload.get("candidates", []) if isinstance(payload.get("candidates"), list) else []:
                if not isinstance(raw_candidate, dict):
                    continue
                tags = normalize_tags(raw_candidate.get("tags", []))
                high_risk = raw_candidate.get("risk") != "low" or "绝对规则" in tags
                if "AI推断" not in tags:
                    tags.append("AI推断")
                if review_all or high_risk:
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
                save_worldbook_atomic(path, book)
            log.info("世界书异步捕获完成: target=%s auto_added=%s pending=%s skipped=%s", path.name, [item["name"] for item in added], [item["name"] for item in pending], skipped)
            return {"added": added, "pending": pending, "skipped": skipped}
