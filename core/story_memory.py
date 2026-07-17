"""Token-budgeted story context, immutable raw slices, and low-frequency compaction."""

from __future__ import annotations

import copy
import json
import math
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from core.ai_engine import robust_json_parse
from core.story_events import StoryEventLedger
from utils.sys_logger import get_logger


log = get_logger()


MEMORY_COMPACTION_PROMPT = """你是 AliveWorld 的故事记忆压缩器。你不续写故事，只整理已经发生的原文。

目标：在明显缩短文本的同时，保留未来继续故事所需的事实、因果、人物承诺、未解决目标、冲突、悬念和进展。不要把世界规则、角色卡资料、暗流实体设定或隐藏影响复制进故事记忆；只记录它们在正文中已经造成、且玩家经历过的结果。

事件规则：
1. story_event 是可跨多个压缩片段延续的故事线程，不是为了凑字段而创建的任务。
2. 日常叙事没有明确长期目标时允许不创建事件。
3. 新事件必须有稳定名称、可理解的核心目标和可验证的完成条件。
4. 只有输入正文已经明确满足完成条件时才能标记 completed，并提供 completion_evidence。
5. 未完成事件只更新 progress；不要因为暂时离开场景就判定完成。
6. 已有事件通过原 id 更新。story_events 只返回本轮新增或发生变化的事件。

输入边界：
1. “本次归档回合”是唯一允许写入摘要、章节脊柱、重点/核心记忆和事件事实的来源。
2. “桥接上下文”仍属于近期完整剧情，只能帮助判断归档片段中的线程是否延续；严禁摘要、转述或提取其中首次出现的事实。
3. source_turns 只能填写本次归档范围内的回合号。桥接回合会由正文以完整原文继续读取，不得提前压入长期记忆。

记忆等级：
- important_memories：转折、承诺、长期变化、关键线索；不要收录普通流水账。
- core_memories：极少数决定身份、关系或整部故事连续性的事实；宁缺毋滥。
- chapter_spine：把旧章节脊柱和本次片段合并成有上限的长期故事骨架，不得无限追加原句。

严格输出 JSON：
{
  "segment_summary": "本片段的详细但压缩后的事实与因果摘要",
  "chapter_spine": "更新后的长期故事骨架",
  "story_events": [
    {"id":"已有事件ID可复用，新事件可空","name":"事件名称","core_goal":"核心目标","completion_condition":"完成标准","progress":"当前进展","status":"active|paused|completed","completion_evidence":"仅完成时填写","source_turns":[1,2],"related_influence_ids":[]}
  ],
  "important_memories": ["重点记忆"],
  "core_memories": ["核心记忆"]
}
"""


MIN_FORCE_ARCHIVE_TOKENS = 300
TINY_BOOTSTRAP_SEGMENT_TOKENS = 128


def estimate_tokens(value: Any) -> int:
    """Dependency-free conservative token estimate for mixed Chinese/Latin text."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if not text:
        return 0
    cjk = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))
    latin_chunks = re.findall(r"[A-Za-z0-9_]+", text)
    latin = sum(max(1, math.ceil(len(chunk) / 4)) for chunk in latin_chunks)
    punctuation = len(re.findall(r"[^\s\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaffA-Za-z0-9_]", text))
    return max(1, cjk + latin + math.ceil(punctuation / 2))


def _bounded_text(value: Any, *, character_limit: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= character_limit else text[:character_limit - 1].rstrip() + "…"


def _unique_text(items: Any, *, limit: int) -> list[str]:
    result: list[str] = []
    for item in items if isinstance(items, list) else []:
        text = _bounded_text(" ".join(str(item).split()), character_limit=500)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _truncate_to_tokens(text: str, token_limit: int) -> str:
    if token_limit <= 0:
        return ""
    if estimate_tokens(text) <= token_limit:
        return text
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if estimate_tokens(text[:middle]) <= token_limit:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip() + "…"


@dataclass(frozen=True)
class MemoryBudget:
    context_limit: int = 32768
    history_high_water: int = 0
    history_low_water: int = 0
    bridge_tokens: int = 0
    min_hot_turns: int = 4

    @classmethod
    def from_context_limit(cls, context_limit: Any) -> "MemoryBudget":
        try:
            limit = int(context_limit)
        except (TypeError, ValueError):
            limit = 32768
        limit = max(8192, min(1_000_000, limit))
        high = max(3000, min(32000, int(limit * 0.38)))
        low = max(1800, int(high * 0.55))
        bridge = max(500, min(2400, int(high * 0.10)))
        return cls(limit, high, low, bridge, 4)

    def to_dict(self) -> dict[str, int]:
        return {
            "context_limit": self.context_limit,
            "history_high_water": self.history_high_water,
            "history_low_water": self.history_low_water,
            "bridge_tokens": self.bridge_tokens,
            "min_hot_turns": self.min_hot_turns,
        }


def normalize_story_turns(turns: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    next_id = 0
    for raw in turns if isinstance(turns, list) else []:
        if isinstance(raw, str):
            item = {"turn_id": next_id, "text": raw}
        elif isinstance(raw, dict):
            item = dict(raw)
        else:
            continue
        try:
            turn_id = int(item.get("turn_id", next_id))
        except (TypeError, ValueError):
            turn_id = next_id
        text = str(item.get("text") or "").strip()
        if not text:
            player = str(item.get("player", "")).strip()
            story = str(item.get("story", "")).strip()
            text = f"玩家：{player}\n结果：{story}".strip()
        if not text:
            continue
        normalized.append({
            "turn_id": turn_id,
            "player": str(item.get("player", "")),
            "story": str(item.get("story", "")),
            "text": text,
            "token_estimate": int(item.get("token_estimate") or estimate_tokens(text)),
            "source_message_ids": [str(value) for value in item.get("source_message_ids", []) if str(value).strip()] if isinstance(item.get("source_message_ids"), list) else [],
        })
        next_id = max(next_id, turn_id + 1)
    normalized.sort(key=lambda item: item["turn_id"])
    return normalized


class StoryMemoryManager:
    INDEX_VERSION = 2

    def __init__(self, save_dir: str = "", ai_engine=None, *, context_limit: int = 32768):
        self.save_dir = Path(save_dir) if save_dir else None
        self.ai_engine = ai_engine
        self.budget = MemoryBudget.from_context_limit(context_limit)
        self._lock = threading.RLock()
        self._running = False
        self._last_error = ""
        self.index = self._load_index()

    @property
    def memory_dir(self) -> Path | None:
        return self.save_dir / "memory" if self.save_dir else None

    @property
    def index_path(self) -> Path | None:
        return self.memory_dir / "index.json" if self.memory_dir else None

    def set_runtime(self, *, save_dir: str | None = None, ai_engine=None, context_limit: Any = None) -> None:
        with self._lock:
            if save_dir is not None and (not self.save_dir or Path(save_dir) != self.save_dir):
                self.save_dir = Path(save_dir) if save_dir else None
                self.index = self._load_index()
            if ai_engine is not None:
                self.ai_engine = ai_engine
            if context_limit is not None:
                self.budget = MemoryBudget.from_context_limit(context_limit)

    def _empty_index(self) -> dict[str, Any]:
        return {
            "version": self.INDEX_VERSION,
            "archived_until_turn": -1,
            "chapter_spine": "",
            "segments": [],
            "story_events": [],
            "important_memories": [],
            "core_memories": [],
            "last_compacted_at": "",
        }

    def _load_index(self) -> dict[str, Any]:
        path = self.index_path
        if not path or not path.exists():
            return self._empty_index()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw_segments = raw.get("segments", []) if isinstance(raw, dict) else []
            if (
                isinstance(raw_segments, list)
                and len(raw_segments) == 1
                and int(raw.get("archived_until_turn", -1)) == 0
                and int(raw_segments[0].get("source_token_estimate", 0)) < TINY_BOOTSTRAP_SEGMENT_TOKENS
            ):
                log.warning("忽略旧版无意义开场压缩索引，恢复使用完整原文: %s", path)
                return self._empty_index()
            index = self._empty_index()
            index.update(raw if isinstance(raw, dict) else {})
            index["segments"] = list(index.get("segments", [])) if isinstance(index.get("segments"), list) else []
            index["story_events"] = StoryEventLedger(index.get("story_events", [])).export()
            return index
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            log.warning("故事记忆索引读取失败，回退完整原文: %s", exc)
            return self._empty_index()

    def import_fallback(self, data: Any) -> None:
        if self.index.get("segments") or not isinstance(data, dict):
            return
        with self._lock:
            index = self._empty_index()
            index.update(copy.deepcopy(data))
            index["segments"] = list(index.get("segments", [])) if isinstance(index.get("segments"), list) else []
            index["story_events"] = StoryEventLedger(index.get("story_events", [])).export()
            self.index = index

    def export_state(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self.index)

    @staticmethod
    def append_turn(turns: list[dict[str, Any]], player: str, story: str, *, source_message_ids: Iterable[str] = ()) -> dict[str, Any]:
        normalized = normalize_story_turns(turns)
        turn_id = (normalized[-1]["turn_id"] + 1) if normalized else 0
        text = f"玩家：{player}\n结果：{story}".strip()
        item = {
            "turn_id": turn_id, "player": player, "story": story, "text": text,
            "token_estimate": estimate_tokens(text),
            "source_message_ids": [str(value) for value in source_message_ids if str(value).strip()],
        }
        turns.append(item)
        return item

    def _raw_turns(self, turns: Any) -> list[dict[str, Any]]:
        archived_value = self.index.get("archived_until_turn", -1)
        archived = int(-1 if archived_value is None else archived_value)
        return [turn for turn in normalize_story_turns(turns) if turn["turn_id"] > archived]

    def _render_memory(self) -> str:
        candidates: list[str] = []
        core = _unique_text(self.index.get("core_memories", []), limit=20)
        if core:
            candidates.append("【核心记忆】\n" + "\n".join(f"- {item}" for item in core))
        events = StoryEventLedger(self.index.get("story_events", [])).context()
        if events:
            candidates.append("【尚未解决的故事线程】\n" + events)
        spine = str(self.index.get("chapter_spine", "")).strip()
        if spine:
            candidates.append("【长期故事脊柱】\n" + spine)
        important = _unique_text(self.index.get("important_memories", []), limit=30)
        if important:
            candidates.append("【重点记忆】\n" + "\n".join(f"- {item}" for item in important))
        recent_segments = self.index.get("segments", [])[-2:]
        summaries = [str(item.get("summary", "")).strip() for item in recent_segments if isinstance(item, dict)]
        if any(summaries):
            candidates.append("【近期压缩片段】\n" + "\n".join(f"- {item}" for item in summaries if item))
        token_limit = max(1500, min(8000, int(self.budget.context_limit * 0.18)))
        parts: list[str] = []
        used = 0
        for candidate in candidates:
            remaining = token_limit - used
            if remaining <= 0:
                break
            bounded = _truncate_to_tokens(candidate, remaining)
            if bounded:
                parts.append(bounded)
                used += estimate_tokens(bounded)
        return "\n\n".join(parts)

    def build_context(self, turns: Any, *, compression_enabled: bool) -> str:
        with self._lock:
            memory = self._render_memory()
            raw = self._raw_turns(turns)
            if not compression_enabled:
                raw = raw[-3:]
            else:
                bounded: list[dict[str, Any]] = []
                tokens = 0
                for item in reversed(raw):
                    if bounded and tokens + item["token_estimate"] > self.budget.history_high_water:
                        break
                    bounded.append(item)
                    tokens += item["token_estimate"]
                raw = list(reversed(bounded))
        recent = "\n\n".join(f"【回合 {item['turn_id']}】\n{item['text']}" for item in raw)
        if memory and recent:
            return memory + "\n\n【近期完整剧情】\n" + recent
        return memory or recent

    def _plan(self, turns: Any, *, force: bool = False) -> dict[str, Any] | None:
        raw = self._raw_turns(turns)
        total = sum(item["token_estimate"] for item in raw)
        if not force and total < self.budget.history_high_water:
            return None
        min_hot = min(self.budget.min_hot_turns, max(1, len(raw) // 2))
        max_archive_count = len(raw) - min_hot
        if max_archive_count <= 0:
            return None
        desired_archive = max(1, total - self.budget.history_low_water)
        if force:
            desired_archive = max(desired_archive, MIN_FORCE_ARCHIVE_TOKENS)
        archive: list[dict[str, Any]] = []
        archived_tokens = 0
        for item in raw[:max_archive_count]:
            archive.append(item)
            archived_tokens += item["token_estimate"]
            if archived_tokens >= desired_archive:
                break
        if not archive:
            return None
        if force and archived_tokens < MIN_FORCE_ARCHIVE_TOKENS:
            return None
        remaining = raw[len(archive):]
        bridge: list[dict[str, Any]] = []
        bridge_tokens = 0
        for item in remaining:
            if bridge and bridge_tokens >= self.budget.bridge_tokens:
                break
            bridge.append(item)
            bridge_tokens += item["token_estimate"]
        return {
            "archive": copy.deepcopy(archive),
            "bridge": copy.deepcopy(bridge),
            "total_tokens": total,
            "archived_tokens": archived_tokens,
            "remaining_tokens": total - archived_tokens,
        }

    def status(self, turns: Any) -> dict[str, Any]:
        with self._lock:
            raw = self._raw_turns(turns)
            return {
                "running": self._running,
                "last_error": self._last_error,
                "raw_turn_count": len(raw),
                "raw_token_estimate": sum(item["token_estimate"] for item in raw),
                "archived_until_turn": int(-1 if self.index.get("archived_until_turn", -1) is None else self.index.get("archived_until_turn", -1)),
                "segment_count": len(self.index.get("segments", [])),
                "active_event_count": len(StoryEventLedger(self.index.get("story_events", [])).active()),
                "last_compacted_at": self.index.get("last_compacted_at", ""),
                "budget": self.budget.to_dict(),
            }

    def schedule(self, turns: Any, *, enabled: bool) -> bool:
        if not enabled or not self.ai_engine or not self.save_dir:
            return False
        with self._lock:
            if self._running:
                return False
            plan = self._plan(turns)
            if not plan:
                return False
            self._running = True
            snapshot = copy.deepcopy(self.index)
        thread = threading.Thread(
            target=self._compact_worker,
            args=(plan, snapshot),
            name="story-memory-compaction",
            daemon=True,
        )
        thread.start()
        return True

    def compact_now(self, turns: Any, *, force: bool = False) -> dict[str, Any]:
        if not self.ai_engine:
            return {"started": False, "error": "未配置压缩模型"}
        with self._lock:
            if self._running:
                return {"started": False, "error": "压缩任务正在运行"}
            plan = self._plan(turns, force=force)
            if not plan:
                return {"started": False, "reason": "尚未达到水位，或没有可安全归档的完整回合"}
            self._running = True
            snapshot = copy.deepcopy(self.index)
        return self._compact_worker(plan, snapshot)

    def _compact_worker(self, plan: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        archive = plan["archive"]
        start_turn, end_turn = archive[0]["turn_id"], archive[-1]["turn_id"]
        try:
            ledger = StoryEventLedger(snapshot.get("story_events", []))
            active_events = sorted(ledger.active(), key=lambda item: (item.updated_turn, item.created_turn), reverse=True)[:30]
            prompt = (
                f"【已有章节脊柱】\n{snapshot.get('chapter_spine', '') or '（无）'}\n"
                f"【已有未解决事件】\n{json.dumps([event.to_dict() for event in active_events], ensure_ascii=False)}\n"
                f"【本次归档回合 {start_turn}-{end_turn}】\n{json.dumps(archive, ensure_ascii=False)}\n"
                f"【与热窗口相接的桥接上下文，仅用于判断延续关系】\n{json.dumps(plan['bridge'], ensure_ascii=False)}"
            )
            raw, error = self.ai_engine.chat_json(
                MEMORY_COMPACTION_PROMPT,
                prompt,
                temp=0.2,
                max_tokens=2600,
                trace_label="故事记忆压缩",
            )
            if error or not raw:
                raise RuntimeError(error or "压缩模型返回空内容")
            payload = robust_json_parse(raw)
            if not isinstance(payload, dict):
                raise ValueError("压缩结果必须是 JSON 对象")
            summary = _bounded_text(payload.get("segment_summary", ""), character_limit=6000)
            if not summary:
                raise ValueError("压缩结果缺少 segment_summary")
            event_updates = []
            for raw_event in payload.get("story_events", []) if isinstance(payload.get("story_events"), list) else []:
                if not isinstance(raw_event, dict):
                    continue
                event = dict(raw_event)
                event["source_turns"] = [
                    turn_id for value in event.get("source_turns", [])
                    if str(value).lstrip("-").isdigit()
                    and start_turn <= (turn_id := int(value)) <= end_turn
                ]
                event_updates.append(event)
            ledger.reconcile(event_updates, current_turn=end_turn)
            segment_name = f"turn_{start_turn:06d}-{end_turn:06d}.json"
            segment_payload = {
                "version": self.INDEX_VERSION,
                "start_turn": start_turn,
                "end_turn": end_turn,
                "source_token_estimate": plan["archived_tokens"],
                "turns": archive,
                "summary": summary,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            new_index = copy.deepcopy(snapshot)
            new_index["version"] = self.INDEX_VERSION
            new_index["archived_until_turn"] = end_turn
            new_index["chapter_spine"] = _bounded_text(
                payload.get("chapter_spine") or snapshot.get("chapter_spine") or summary,
                character_limit=8000,
            )
            new_index["story_events"] = ledger.export()
            new_index["important_memories"] = _unique_text(
                list(snapshot.get("important_memories", [])) + list(payload.get("important_memories", []) if isinstance(payload.get("important_memories"), list) else []),
                limit=30,
            )
            new_index["core_memories"] = _unique_text(
                list(snapshot.get("core_memories", [])) + list(payload.get("core_memories", []) if isinstance(payload.get("core_memories"), list) else []),
                limit=20,
            )
            segments = list(new_index.get("segments", [])) if isinstance(new_index.get("segments"), list) else []
            segments.append({
                "start_turn": start_turn,
                "end_turn": end_turn,
                "file": f"segments/{segment_name}",
                "summary": summary,
                "source_token_estimate": plan["archived_tokens"],
            })
            new_index["segments"] = segments
            new_index["last_compacted_at"] = datetime.now().isoformat(timespec="seconds")
            if not self.memory_dir or not self.index_path:
                raise RuntimeError("存档目录不可用")
            _atomic_write_json(self.memory_dir / "segments" / segment_name, segment_payload)
            _atomic_write_json(self.index_path, new_index)
            with self._lock:
                current_archived = self.index.get("archived_until_turn", -1)
                snapshot_archived = snapshot.get("archived_until_turn", -1)
                if int(-1 if current_archived is None else current_archived) <= int(-1 if snapshot_archived is None else snapshot_archived):
                    self.index = new_index
                self._last_error = ""
            log.info(
                "故事记忆压缩完成: turns=%s-%s source_tokens=%s remaining_tokens=%s events=%s",
                start_turn, end_turn, plan["archived_tokens"], plan["remaining_tokens"], len(ledger.active()),
            )
            return {"started": True, "completed": True, "start_turn": start_turn, "end_turn": end_turn, "summary": summary}
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
            log.warning("故事记忆压缩失败，继续使用完整原文上下文: %s", exc)
            return {"started": True, "completed": False, "error": str(exc)}
        finally:
            with self._lock:
                self._running = False
