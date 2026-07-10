"""暗流实体的领域模型。

此模块只负责实体数据及兼容转换，不负责 YAML、提示词或回合调度。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


@dataclass
class Entity:
    """具有长期影响的幕后力量。

    ``goal`` 是 v1.0.0 的旧字段；读取时会兼容为 ``motive``，写回时只使用新字段。
    ``extra`` 保留尚未纳入契约的 YAML 字段，避免同步本局实体时丢失用户自定义信息。
    """

    name: str
    motive: str = "未知动机"
    status: str = ""
    recent_actions: List[Any] = field(default_factory=list)
    plans: List[Any] = field(default_factory=list)
    mechanisms: List[Any] = field(default_factory=list)
    triggers: List[Any] = field(default_factory=list)
    relationships: Dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5
    is_active: bool = True
    tags: List[Any] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict, repr=False)

    _KNOWN_FIELDS = {
        "name", "motive", "goal", "status", "recent_actions", "plans", "mechanisms",
        "triggers", "relationships", "importance", "is_active", "tags",
    }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Entity":
        raw = dict(data or {})
        try:
            importance = float(raw.get("importance", 0.5))
        except (TypeError, ValueError):
            importance = 0.5

        return cls(
            name=_as_text(raw.get("name"), "未知实体"),
            motive=_as_text(raw.get("motive", raw.get("goal")), "未知动机"),
            status=_as_text(raw.get("status")),
            recent_actions=_as_list(raw.get("recent_actions")),
            plans=_as_list(raw.get("plans")),
            mechanisms=_as_list(raw.get("mechanisms")),
            triggers=_as_list(raw.get("triggers")),
            relationships=dict(raw.get("relationships") or {}) if isinstance(raw.get("relationships"), dict) else {},
            importance=max(0.0, min(1.0, importance)),
            is_active=bool(raw.get("is_active", True)),
            tags=_as_list(raw.get("tags")),
            extra={key: value for key, value in raw.items() if key not in cls._KNOWN_FIELDS},
        )

    def apply_update(self, update: Dict[str, Any]) -> None:
        """应用 Overseer 给出的部分更新，忽略未知字段以保持模型边界。"""
        if "motive" in update or "goal" in update:
            self.motive = _as_text(update.get("motive", update.get("goal")), self.motive)
        if "status" in update:
            self.status = _as_text(update["status"])

        for field_name in ("recent_actions", "plans", "mechanisms", "triggers", "tags"):
            if field_name in update:
                setattr(self, field_name, _as_list(update[field_name]))

        if "relationships" in update and isinstance(update["relationships"], dict):
            self.relationships = dict(update["relationships"])
        if "importance" in update:
            try:
                self.importance = max(0.0, min(1.0, float(update["importance"])))
            except (TypeError, ValueError):
                pass
        if "is_active" in update:
            self.is_active = bool(update["is_active"])

    def add_recent_action(self, action: str, limit: int = 8) -> None:
        if action:
            self.recent_actions.append(action)
            self.recent_actions = self.recent_actions[-limit:]

    def apply_action(self, action: Dict[str, Any]) -> None:
        """合并一次实体行动产生的增量，不覆盖既有长期计划。"""
        action_text = _as_text(action.get("action"))
        self.add_recent_action(action_text)
        if "status" in action:
            self.status = _as_text(action["status"])

        for source, destination in (
            ("new_plans", "plans"),
            ("new_mechanisms", "mechanisms"),
            ("new_triggers", "triggers"),
        ):
            if source not in action:
                continue
            current = getattr(self, destination)
            for item in _as_list(action[source]):
                if item not in current:
                    current.append(item)

        if isinstance(action.get("relationship_updates"), dict):
            self.relationships.update(action["relationship_updates"])

    def to_dict(self) -> Dict[str, Any]:
        data = dict(self.extra)
        data.update({
            "name": self.name,
            "motive": self.motive,
            "status": self.status,
            "recent_actions": self.recent_actions,
            "plans": self.plans,
            "mechanisms": self.mechanisms,
            "triggers": self.triggers,
            "relationships": self.relationships,
            "importance": self.importance,
            "is_active": self.is_active,
            "tags": self.tags,
        })
        return data

    def prompt_summary(self) -> str:
        recent = "；".join(_as_text(item) for item in self.recent_actions[-2:]) or "无"
        plan = "；".join(_as_text(item) for item in self.plans[-2:]) or "无"
        return f"- 【{self.name}】动机：{self.motive}；状态：{self.status or '未知'}；近期行动：{recent}；计划：{plan}"


def active_entities(entities: Iterable[Entity]) -> List[Entity]:
    return [entity for entity in entities if entity.is_active]
