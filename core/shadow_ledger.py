"""影子账本及其受限上下文投影。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List


@dataclass
class ShadowLedgerEntry:
    tick: int = 0
    kind: str = "event"
    entity: str = ""
    summary: str = ""
    clues: List[Any] = field(default_factory=list)

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
            clues=list(data.get("clues", []) or []),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "kind": self.kind,
            "entity": self.entity,
            "summary": self.summary,
            "clues": self.clues,
        }

    def to_context_line(self) -> str:
        if self.entity:
            return f"[Tick {self.tick}] {self.entity}：{self.summary}"
        return self.summary


class ShadowLedger:
    def __init__(self, entries: Iterable[Any] = ()):
        self.entries = [ShadowLedgerEntry.from_data(entry) for entry in entries]

    def record(self, tick: int, kind: str, entity: str, summary: str, clues: Iterable[Any] = ()) -> None:
        if summary:
            self.entries.append(ShadowLedgerEntry(tick, kind, entity, summary, list(clues)))

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
