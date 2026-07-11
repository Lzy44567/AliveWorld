"""Structured hidden-world influences with deterministic lifecycle handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List
from uuid import uuid4


VALID_TYPES = {"one_shot", "persistent", "evolving"}
VALID_CONSUME_MODES = {"on_success", "on_attempt", "after_n", "never"}
VALID_DEATH_ACTIONS = {"remove", "release", "keep"}


def _list(value):
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _source_link(value):
    if isinstance(value, str):
        return {"entity": value, "life_link_strength": 0.5, "on_source_death": "keep"}
    raw = dict(value or {})
    try:
        strength = max(0.0, min(1.0, float(raw.get("life_link_strength", 0.5))))
    except (TypeError, ValueError):
        strength = 0.5
    action = raw.get("on_source_death", "keep")
    normalized = {
        "entity": str(raw.get("entity", "")),
        "life_link_strength": strength,
        "on_source_death": action if action in VALID_DEATH_ACTIONS else "keep",
    }
    if raw.get("source_dead"):
        normalized["source_dead"] = True
    return normalized


@dataclass
class CausalInfluence:
    id: str = field(default_factory=lambda: f"influence_{uuid4().hex[:10]}")
    source_links: List[Dict[str, Any]] = field(default_factory=list)
    type: str = "persistent"
    summary: str = ""
    condition: str = ""
    effect: str = ""
    status: str = "active"
    created_tick: int = 0
    age_ticks: int = 0
    created_world_time: str = ""
    attempt_count: int = 0
    trigger_count: int = 0
    consume_policy: Dict[str, Any] = field(default_factory=lambda: {"mode": "never", "max_triggers": None})
    tags: List[Any] = field(default_factory=list)
    force_next_turn: bool = False

    @classmethod
    def from_data(cls, data, current_tick=0):
        raw = dict(data or {})
        influence_type = raw.get("type", "persistent")
        policy = dict(raw.get("consume_policy") or {})
        mode = policy.get("mode", "on_success" if influence_type == "one_shot" else "never")
        if mode not in VALID_CONSUME_MODES:
            mode = "never"
        return cls(
            id=str(raw.get("id") or f"influence_{uuid4().hex[:10]}"),
            source_links=[_source_link(item) for item in _list(raw.get("source_links", raw.get("source_entity"))) if item],
            type=influence_type if influence_type in VALID_TYPES else "persistent",
            summary=str(raw.get("summary", "")),
            condition=str(raw.get("condition", "")),
            effect=str(raw.get("effect", "")),
            status=str(raw.get("status", "active")),
            created_tick=int(raw.get("created_tick", current_tick) or 0),
            age_ticks=int(raw.get("age_ticks", 0) or 0),
            created_world_time=str(raw.get("created_world_time", "")),
            attempt_count=int(raw.get("attempt_count", 0) or 0),
            trigger_count=int(raw.get("trigger_count", 0) or 0),
            consume_policy={"mode": mode, "max_triggers": policy.get("max_triggers")},
            tags=_list(raw.get("tags")),
            force_next_turn=bool(raw.get("force_next_turn", False)),
        )

    def to_dict(self):
        return {
            "id": self.id, "source_links": self.source_links, "type": self.type,
            "summary": self.summary, "condition": self.condition, "effect": self.effect,
            "status": self.status, "created_tick": self.created_tick, "age_ticks": self.age_ticks,
            "created_world_time": self.created_world_time, "attempt_count": self.attempt_count,
            "trigger_count": self.trigger_count, "consume_policy": self.consume_policy,
            "tags": self.tags, "force_next_turn": self.force_next_turn,
        }

    def is_active(self):
        return self.status == "active"

    def context_line(self):
        sources = "、".join(link["entity"] for link in self.source_links if link.get("entity")) or "未知来源"
        forced = "；已因来源死亡释放，本回合必须兑现" if self.force_next_turn else ""
        return (
            f"- [{self.id}] 类型={self.type}；来源={sources}；影响={self.summary}；"
            f"条件={self.condition}；后果={self.effect}；已存在{self.age_ticks}回合；"
            f"已判断{self.attempt_count}次；已触发{self.trigger_count}次{forced}"
        )


class CausalLedger:
    def __init__(self, influences: Iterable[Any] = ()):
        self.influences = [CausalInfluence.from_data(item) for item in influences]

    def export(self):
        return [item.to_dict() for item in self.influences]

    def active(self):
        return [item for item in self.influences if item.is_active()]

    def by_id(self, influence_id):
        return next((item for item in self.influences if item.id == influence_id), None)

    def add(self, data, current_tick=0):
        item = CausalInfluence.from_data(data, current_tick=current_tick)
        if not item.summary or self.by_id(item.id):
            return None
        self.influences.append(item)
        return item

    def update(self, data):
        item = self.by_id(str((data or {}).get("id", "")))
        if not item:
            return None
        merged = item.to_dict()
        merged.update({key: value for key, value in data.items() if key != "id"})
        replacement = CausalInfluence.from_data(merged)
        self.influences[self.influences.index(item)] = replacement
        return replacement

    def remove(self, influence_id, status="cancelled"):
        item = self.by_id(influence_id)
        if item:
            item.status = status
        return item

    def advance_turn(self):
        for item in self.active():
            item.age_ticks += 1

    def context(self, character_limit=4000):
        lines = [item.context_line() for item in self.active()]
        text = "\n".join(lines) or "（当前没有潜在暗流影响）"
        return text if len(text) <= character_limit else text[:character_limit] + "…"

    def evaluate_checks(self, checks):
        triggered = []
        checked_ids = set()
        for check in _list(checks):
            if not isinstance(check, dict):
                continue
            item = self.by_id(str(check.get("id", "")))
            if not item or not item.is_active() or item.id in checked_ids:
                continue
            checked_ids.add(item.id)
            item.attempt_count += 1
            condition_met = bool(check.get("condition_met", False)) or item.force_next_turn
            if item.consume_policy.get("mode") == "on_attempt":
                item.status = "consumed"
            if condition_met:
                triggered.append({
                    "id": item.id, "summary": item.summary, "effect": item.effect,
                    "reason": str(check.get("reason", "条件满足")),
                })

        for item in self.active():
            if item.force_next_turn and item.id not in checked_ids:
                item.attempt_count += 1
                triggered.append({"id": item.id, "summary": item.summary, "effect": item.effect, "reason": "来源死亡释放"})
        return triggered

    def resolve(self, resolutions):
        resolved = []
        for result in _list(resolutions):
            if not isinstance(result, dict):
                continue
            item = self.by_id(str(result.get("id", "")))
            if not item or item.status not in {"active", "consumed"}:
                continue
            item.trigger_count += 1
            item.force_next_turn = False
            mode = item.consume_policy.get("mode", "never")
            maximum = item.consume_policy.get("max_triggers")
            if mode == "on_success" or (mode == "after_n" and maximum is not None and item.trigger_count >= int(maximum)):
                item.status = "consumed"
            resolved.append(item)
        return resolved

    def handle_source_death(self, entity_name):
        released, removed = [], []
        for item in self.active():
            matching = [link for link in item.source_links if link.get("entity") == entity_name]
            if not matching:
                continue
            if any(link.get("on_source_death") == "release" for link in matching):
                item.force_next_turn = True
                released.append(item)
            retained_matching = []
            for link in matching:
                if link.get("on_source_death") != "remove":
                    retained_matching.append({**link, "source_dead": True})
            other_links = [link for link in item.source_links if link.get("entity") != entity_name]
            item.source_links = other_links + retained_matching
            if matching and all(link.get("on_source_death") == "remove" for link in matching) and not item.source_links:
                item.status = "cancelled"
                item.force_next_turn = False
                removed.append(item)
        return {"released": released, "removed": removed}

    def refs_for_entity(self, entity_name):
        refs = []
        for item in self.influences:
            for link in item.source_links:
                if link.get("entity") == entity_name:
                    refs.append({
                        "id": item.id, "summary": item.summary, "status": item.status,
                        "life_link_strength": link.get("life_link_strength", 0.5),
                        "on_source_death": link.get("on_source_death", "keep"),
                    })
        return refs
