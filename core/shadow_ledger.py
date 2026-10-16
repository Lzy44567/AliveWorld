"""影子账本及其受限上下文投影。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _detail_clues(details: Dict[str, Any]) -> List[str]:
    clues = []
    for label, field in (("计划", "new_plans"), ("机制", "new_mechanisms")):
        for value in _as_list(details.get(field))[:2]:
            clues.append(f"{label}：{value}")

    for trigger in _as_list(details.get("new_triggers"))[:2]:
        if isinstance(trigger, dict):
            condition = trigger.get("condition", "未说明条件")
            result = trigger.get("result", "未说明后果")
            clues.append(f"触发：{condition}→{result}")
        else:
            clues.append(f"触发：{trigger}")

    for name, relation in list((details.get("relationship_updates") or {}).items())[:2]:
        clues.append(f"关系：{name}={relation}")
    return clues


@dataclass
class ShadowLedgerEntry:
    tick: int = 0
    kind: str = "event"
    entity: str = ""
    summary: str = ""
    clues: List[Any] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_data(cls, data: Any) -> "ShadowLedgerEntry":
        if isinstance(data, str):
            return cls(summary=data)
        if not isinstance(data, dict):
            return cls(summary=str(data))
        return cls(
            tick=int(data.get("tick", 0) or 0),
            kind=str(data.get("kind", "event")),
            entity=str(data.get("entity", "")),
            summary=str(data.get("summary", "")),
            clues=_as_list(data.get("clues")),
            details=dict(data.get("details") or {}) if isinstance(data.get("details"), dict) else {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "kind": self.kind,
            "entity": self.entity,
            "summary": self.summary,
            "clues": self.clues,
            "details": self.details,
        }

    def to_context_line(self) -> str:
        prefix = f"[Tick {self.tick}] {self.entity}：{self.summary}" if self.entity else self.summary
        labels = {'plan': '计划，尚未执行', 'action': '已执行行动，不代表目标成功', 'fact': '已发生事实'}
        prefix = f"【{labels.get(self.kind, self.kind)}】" + prefix
        if self.details.get('world_time'):
            prefix += f"；故事时间：{self.details['world_time']}"
        if self.details.get('basis'):
            prefix += f"；依据：{self.details['basis']}"
        known = self.details.get('known_to', [])
        prefix += '；明确知情者：' + ('、'.join(known) if known else '未记录，不默认角色已知')
        all_clues = [str(clue) for clue in self.clues] + _detail_clues(self.details)
        clue_text = "；".join(all_clues[:4])
        return f"{prefix}；可能的发现线索（非已获知）：{clue_text}" if clue_text else prefix


class ShadowLedger:
    def __init__(self, entries: Iterable[Any] = ()):
        self.entries = [ShadowLedgerEntry.from_data(entry) for entry in entries]

    def record(
        self,
        tick: int,
        kind: str,
        entity: str,
        summary: str,
        clues: Iterable[Any] = (),
        details: Dict[str, Any] | None = None,
    ) -> None:
        if summary:
            self.entries.append(ShadowLedgerEntry(tick, kind, entity, summary, _as_list(clues), dict(details or {})))

    def export(self) -> List[Dict[str, Any]]:
        return [entry.to_dict() for entry in self.entries]

    def context(self, entry_limit: int = 3, character_limit: int = 1200) -> str:
        if not self.entries:
            return "（世界目前风平浪静）"

        lines = [entry.to_context_line() for entry in self.entries[-entry_limit:]]
        text = "\n".join(lines)
        if len(text) <= character_limit:
            return text
        return "…" + text[-(character_limit - 1):]
