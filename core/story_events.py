"""Story-thread records produced by low-frequency memory compaction.

These records reuse the lifecycle vocabulary of the causal ledger without
pretending that a narrative goal and a hidden influence have the same effect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
from uuid import uuid4


VALID_STATUSES = {"active", "paused", "completed", "cancelled"}


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _clean_turns(value: Any) -> list[int]:
    turns: list[int] = []
    for item in _list(value):
        try:
            turn = int(item)
        except (TypeError, ValueError):
            continue
        if turn >= 0 and turn not in turns:
            turns.append(turn)
    return turns[-20:]


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


@dataclass
class StoryEvent:
    id: str = field(default_factory=lambda: f"event_{uuid4().hex[:10]}")
    name: str = ""
    core_goal: str = ""
    completion_condition: str = ""
    progress: str = ""
    status: str = "active"
    created_turn: int = 0
    updated_turn: int = 0
    age_turns: int = 0
    source_turns: list[int] = field(default_factory=list)
    related_influence_ids: list[str] = field(default_factory=list)
    completion_evidence: str = ""

    @classmethod
    def from_data(cls, data: Any, *, current_turn: int = 0) -> "StoryEvent":
        raw = dict(data or {})
        status = str(raw.get("status", "active")).strip().lower()
        if status not in VALID_STATUSES:
            status = "active"
        created_turn = _to_int(raw.get("created_turn", current_turn), current_turn)
        updated_turn = _to_int(raw.get("updated_turn", current_turn), current_turn)
        evidence = str(raw.get("completion_evidence", "")).strip()
        if status == "completed" and not evidence:
            status = "active"
        return cls(
            id=str(raw.get("id") or f"event_{uuid4().hex[:10]}"),
            name=_text(raw.get("name", ""), 120),
            core_goal=_text(raw.get("core_goal", ""), 500),
            completion_condition=_text(raw.get("completion_condition", ""), 500),
            progress=_text(raw.get("progress", ""), 1000),
            status=status,
            created_turn=created_turn,
            updated_turn=updated_turn,
            age_turns=max(0, _to_int(raw.get("age_turns", max(0, current_turn - created_turn)), max(0, current_turn - created_turn))),
            source_turns=_clean_turns(raw.get("source_turns")),
            related_influence_ids=[str(item) for item in _list(raw.get("related_influence_ids")) if str(item).strip()][:20],
            completion_evidence=_text(evidence, 500),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "core_goal": self.core_goal,
            "completion_condition": self.completion_condition,
            "progress": self.progress,
            "status": self.status,
            "created_turn": self.created_turn,
            "updated_turn": self.updated_turn,
            "age_turns": self.age_turns,
            "source_turns": self.source_turns,
            "related_influence_ids": self.related_influence_ids,
            "completion_evidence": self.completion_evidence,
        }

    def context_line(self) -> str:
        progress = f"；进展={self.progress}" if self.progress else ""
        return f"- [{self.id}] {self.name}；目标={self.core_goal}；完成标准={self.completion_condition}{progress}"


class StoryEventLedger:
    def __init__(self, events: Iterable[Any] = ()):
        self.events = [StoryEvent.from_data(item) for item in events]

    def export(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]

    def active(self) -> list[StoryEvent]:
        return [event for event in self.events if event.status in {"active", "paused"}]

    def by_id(self, event_id: str) -> StoryEvent | None:
        return next((event for event in self.events if event.id == event_id), None)

    def _match(self, raw: dict[str, Any]) -> StoryEvent | None:
        event_id = str(raw.get("id", "")).strip()
        if event_id:
            found = self.by_id(event_id)
            if found:
                return found
        name = " ".join(str(raw.get("name", "")).split()).casefold()
        goal = " ".join(str(raw.get("core_goal", "")).split()).casefold()
        if not name:
            return None
        return next(
            (
                event for event in self.active()
                if " ".join(event.name.split()).casefold() == name
                and (not goal or " ".join(event.core_goal.split()).casefold() == goal)
            ),
            None,
        )

    def reconcile(self, updates: Any, *, current_turn: int) -> list[StoryEvent]:
        changed: list[StoryEvent] = []
        for value in _list(updates):
            if not isinstance(value, dict):
                continue
            raw = dict(value)
            existing = self._match(raw)
            if existing:
                merged = existing.to_dict()
                updates = {key: value for key, value in raw.items() if key != "id" and value not in (None, "")}
                if existing.core_goal:
                    updates.pop("core_goal", None)
                if existing.completion_condition:
                    updates.pop("completion_condition", None)
                if existing.status == "completed":
                    updates["status"] = "completed"
                    updates["completion_evidence"] = existing.completion_evidence
                updates["source_turns"] = _clean_turns(existing.source_turns + _clean_turns(raw.get("source_turns")))
                updates["related_influence_ids"] = list(dict.fromkeys(
                    existing.related_influence_ids
                    + [str(item) for item in _list(raw.get("related_influence_ids")) if str(item).strip()]
                ))
                merged.update(updates)
                merged["id"] = existing.id
                merged["created_turn"] = existing.created_turn
                merged["updated_turn"] = current_turn
                merged["age_turns"] = max(0, current_turn - existing.created_turn)
                replacement = StoryEvent.from_data(merged, current_turn=current_turn)
                self.events[self.events.index(existing)] = replacement
                changed.append(replacement)
                continue
            candidate = StoryEvent.from_data({**raw, "updated_turn": current_turn}, current_turn=current_turn)
            if not candidate.name or not candidate.core_goal or not candidate.completion_condition:
                continue
            self.events.append(candidate)
            changed.append(candidate)
        return changed

    def context(self, *, limit: int = 12) -> str:
        active = sorted(self.active(), key=lambda item: (item.updated_turn, item.created_turn), reverse=True)[:limit]
        return "\n".join(event.context_line() for event in active)
