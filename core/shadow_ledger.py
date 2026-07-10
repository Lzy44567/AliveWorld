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
        clue_text = "；".join(str(clue) for clue in self.clues[:3])
        return f"{prefix}；线索：{clue_text}" if clue_text else prefix


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
