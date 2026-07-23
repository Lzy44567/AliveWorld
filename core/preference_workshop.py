"""Transactional, persisted draft engine for the user preference workshop."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.user_preferences import (
    VALID_CATEGORIES,
    VALID_POLARITIES,
    VALID_STATUSES,
    UserPreferenceRepository,
)


ALLOWED_OPERATIONS = {"add_preference", "update_preference", "set_status", "delete_preference"}
EDITABLE_FIELDS = {"statement", "category", "polarity", "status", "sensitive"}


class PreferenceWorkshopError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _revision(preferences: list[dict[str, Any]]) -> str:
    encoded = json.dumps(preferences, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _clean(value: Any, limit: int = 400) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _find(preferences: list[dict[str, Any]], preference_id: str) -> tuple[int, dict[str, Any]]:
    for index, item in enumerate(preferences):
        if item.get("id") == preference_id:
            return index, item
    raise PreferenceWorkshopError(f"偏好草稿中不存在 {preference_id}")


def _normalize_item(raw: dict[str, Any], *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    item = deepcopy(existing or {})
    statement = _clean(raw.get("statement", item.get("statement", "")), 400)
    if not statement:
        raise PreferenceWorkshopError("偏好内容不能为空")
    category = str(raw.get("category", item.get("category", "other"))).lower()
    polarity = str(raw.get("polarity", item.get("polarity", "prefer"))).lower()
    status = str(raw.get("status", item.get("status", "candidate"))).lower()
    item.update({
        "id": str(item.get("id") or raw.get("id") or f"preference_workshop_{uuid4().hex[:12]}"),
        "statement": statement,
        "category": category if category in VALID_CATEGORIES else "other",
        "polarity": polarity if polarity in VALID_POLARITIES else "prefer",
        "status": status if status in VALID_STATUSES else "candidate",
        "sensitive": bool(raw.get("sensitive", item.get("sensitive", False))),
        "manual_override": True,
        "source_type": str(item.get("source_type") or "workshop"),
        "confidence": float(item.get("confidence", 0.75 if status == "active" else 0.2)),
        "posterior": float(item.get("posterior", item.get("confidence", 0.75 if status == "active" else 0.2))),
        "updated_at": _now(),
    })
    item.setdefault("created_at", _now())
    item.setdefault("evidence_count", 0)
    item.setdefault("evidence", [])
    return item


def apply_preference_operation(preferences: list[dict[str, Any]], operation: dict[str, Any]) -> None:
    op = operation["op"]
    if op == "add_preference":
        preferences.append(_normalize_item(operation.get("preference", {})))
        return
    index, current = _find(preferences, str(operation.get("preference_id", "")))
    if op == "update_preference":
        changes = {key: value for key, value in operation.get("changes", {}).items() if key in EDITABLE_FIELDS}
        preferences[index] = _normalize_item(changes, existing=current)
    elif op == "set_status":
        preferences[index] = _normalize_item({"status": operation.get("status")}, existing=current)
    elif op == "delete_preference":
        preferences.pop(index)


class PreferenceWorkshop:
    def __init__(self, workshop_id: str, profile: dict[str, Any], *, include_sensitive: bool = False):
        self.id = workshop_id
        self.base_preferences = deepcopy(profile.get("preferences", []))
        self.draft = deepcopy(self.base_preferences)
        self.source_revision = _revision(self.base_preferences)
        self.include_sensitive = bool(include_sensitive)
        self.operations: list[dict[str, Any]] = []
        self.proposed: list[dict[str, Any]] = []
        self.pending: list[dict[str, Any]] = []
        self.snapshots: list[dict[str, Any]] = []
        self.messages: list[dict[str, str]] = []
        self.suggested_actions: list[str] = []
        self.dirty = False
        self.published = False
        self.updated_at = _now()

    def touch(self, *, dirty: bool = True) -> None:
        self.dirty = self.dirty or dirty
        if dirty:
            self.published = False
        self.updated_at = _now()

    def _validate(self, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict) or raw.get("op") not in ALLOWED_OPERATIONS:
            raise PreferenceWorkshopError("偏好工坊拒绝了未授权操作")
        operation = deepcopy(raw)
        operation["operation_id"] = str(operation.get("operation_id") or uuid4())
        if operation["op"] == "add_preference":
            operation["preference"] = _normalize_item(operation.get("preference", {}))
        else:
            _find(self.draft, str(operation.get("preference_id", "")))
            if operation["op"] == "update_preference":
                if not isinstance(operation.get("changes"), dict):
                    raise PreferenceWorkshopError("修改偏好必须提供 changes")
                operation["changes"] = {
                    key: value for key, value in operation["changes"].items() if key in EDITABLE_FIELDS
                }
            elif operation["op"] == "set_status":
                if operation.get("status") not in VALID_STATUSES:
                    raise PreferenceWorkshopError("偏好状态无效")
        return operation

    @staticmethod
    def _high_risk(operation: dict[str, Any]) -> bool:
        if operation["op"] == "delete_preference":
            return True
        if operation["op"] == "set_status":
            return operation.get("status") == "active"
        if operation["op"] == "add_preference":
            return operation["preference"].get("status") == "active"
        return operation.get("changes", {}).get("status") == "active"

    def _snapshot(self) -> None:
        self.snapshots.append({"draft": deepcopy(self.draft), "operations": deepcopy(self.operations)})
        self.snapshots = self.snapshots[-50:]

    def propose_operations(self, operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.proposed = [self._validate(item) for item in operations]
        if self.proposed:
            self.touch()
        return deepcopy(self.proposed)

    def clear_proposal(self) -> None:
        self.proposed = []

    def apply_operations(self, operations: list[dict[str, Any]], *, confirm_high_risk: bool = False) -> dict[str, Any]:
        applied = []
        for raw in operations:
            operation = self._validate(raw)
            if self._high_risk(operation) and not confirm_high_risk:
                self.pending.append(operation)
                continue
            self._snapshot()
            apply_preference_operation(self.draft, operation)
            self.operations.append(operation)
            applied.append(operation)
        if applied or self.pending:
            self.touch()
        return {"applied": applied, "pending": deepcopy(self.pending), "draft": deepcopy(self.draft)}

    def approve(self, operation_id: str) -> None:
        for index, operation in enumerate(self.pending):
            if operation.get("operation_id") == operation_id:
                self._snapshot()
                apply_preference_operation(self.draft, operation)
                self.operations.append(operation)
                self.pending.pop(index)
                self.touch()
                return
        raise PreferenceWorkshopError("待确认操作不存在")

    def reject(self, operation_id: str) -> None:
        before = len(self.pending)
        self.pending = [item for item in self.pending if item.get("operation_id") != operation_id]
        if len(self.pending) == before:
            raise PreferenceWorkshopError("待确认操作不存在")
        self.touch()

    def undo(self) -> None:
        if not self.snapshots:
            raise PreferenceWorkshopError("没有可撤销的工坊修改")
        snapshot = self.snapshots.pop()
        self.draft = snapshot["draft"]
        self.operations = snapshot["operations"]
        self.touch()

    def publish(self, repository: UserPreferenceRepository) -> dict[str, Any]:
        current = repository.load()
        merged = deepcopy(current.get("preferences", []))
        for operation in self.operations:
            try:
                apply_preference_operation(merged, operation)
            except PreferenceWorkshopError:
                if operation["op"] != "delete_preference":
                    raise PreferenceWorkshopError("正式偏好卡已发生冲突，请关闭后重新进入工坊")
        profile = repository.publish_preferences(merged)
        self.base_preferences = deepcopy(profile["preferences"])
        self.draft = deepcopy(profile["preferences"])
        self.source_revision = _revision(self.base_preferences)
        self.operations = []
        self.pending = []
        self.proposed = []
        self.snapshots = []
        self.dirty = False
        self.published = True
        self.touch(dirty=False)
        return profile

    def rebase(self, profile: dict[str, Any]) -> None:
        """Replay draft operations over a newer live preference card."""
        latest = deepcopy(profile.get("preferences", []))
        for operation in self.operations:
            try:
                apply_preference_operation(latest, operation)
            except PreferenceWorkshopError as exc:
                raise PreferenceWorkshopError("正式偏好卡与工坊草稿存在冲突，无法自动合并") from exc
        self.base_preferences = deepcopy(profile.get("preferences", []))
        self.draft = latest
        self.source_revision = _revision(self.base_preferences)
        self.touch()

    def is_based_on(self, profile: dict[str, Any]) -> bool:
        return self.source_revision == _revision(profile.get("preferences", []))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "base_preferences": self.base_preferences, "draft": self.draft,
            "source_revision": self.source_revision, "include_sensitive": self.include_sensitive,
            "operations": self.operations, "proposed": self.proposed, "pending": self.pending,
            "snapshots": self.snapshots, "messages": self.messages,
            "suggested_actions": self.suggested_actions, "dirty": self.dirty,
            "published": self.published, "updated_at": self.updated_at,
        }

    def save_session(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.id}.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PreferenceWorkshop":
        profile = {"preferences": data.get("base_preferences", data.get("draft", []))}
        workshop = cls(str(data["id"]), profile, include_sensitive=bool(data.get("include_sensitive", False)))
        for key in ("draft", "operations", "proposed", "pending", "snapshots", "messages", "suggested_actions"):
            setattr(workshop, key, deepcopy(data.get(key, getattr(workshop, key))))
        workshop.source_revision = str(data.get("source_revision") or workshop.source_revision)
        workshop.dirty = bool(data.get("dirty", False))
        workshop.published = bool(data.get("published", False))
        workshop.updated_at = str(data.get("updated_at") or workshop.updated_at)
        return workshop
