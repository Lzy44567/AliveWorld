"""Transactional draft engine for the worldbook workshop."""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.worldbook import normalize_axioms, normalize_entry, normalize_tags, normalize_worldbook, save_worldbook_atomic


ALLOWED_OPERATIONS = {"add_entry", "update_entry", "deactivate_entry", "request_delete", "delete_entry", "update_overview", "set_axioms"}


class WorkshopError(ValueError):
    pass


def _find_entry(book: dict[str, Any], entry_id: str) -> tuple[int, dict[str, Any]]:
    for index, entry in enumerate(book.get("entries", [])):
        if entry.get("id") == entry_id:
            return index, entry
    raise WorkshopError(f"世界书中不存在条目 {entry_id}")


def _is_high_risk(book: dict[str, Any], operation: dict[str, Any]) -> bool:
    op = operation.get("op")
    if op == "request_delete":
        return True
    if op in {"delete_entry", "set_axioms"}:
        return True
    if op == "add_entry":
        return bool(operation.get("creates_axiom")) or "绝对规则" in normalize_tags(operation.get("entry", {}).get("tags", []))
    if op == "update_entry":
        _, current = _find_entry(book, str(operation.get("entry_id", "")))
        changes = operation.get("changes", {}) if isinstance(operation.get("changes"), dict) else {}
        new_tags = normalize_tags(changes.get("tags", current.get("tags", [])))
        return "绝对规则" in current.get("tags", []) or "绝对规则" in new_tags or bool(operation.get("creates_axiom"))
    return False


class WorldbookWorkshop:
    def __init__(self, workshop_id: str, target_path: Path, source: dict[str, Any]):
        self.id = workshop_id
        self.target_path = Path(target_path)
        self.draft = normalize_worldbook(copy.deepcopy(source))
        self.snapshots: list[dict[str, Any]] = []
        self.pending: list[dict[str, Any]] = []
        self.messages: list[dict[str, str]] = []
        self.dirty = False
        self.published = False
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def touch(self, *, dirty: bool = True) -> None:
        self.dirty = self.dirty or dirty
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def _snapshot(self) -> None:
        self.snapshots.append(copy.deepcopy(self.draft))
        if len(self.snapshots) > 50:
            self.snapshots.pop(0)

    def _validate(self, operation: Any) -> dict[str, Any]:
        if not isinstance(operation, dict) or operation.get("op") not in ALLOWED_OPERATIONS:
            raise WorkshopError("世界书工坊拒绝了未授权操作")
        operation = copy.deepcopy(operation)
        operation["operation_id"] = str(operation.get("operation_id") or uuid.uuid4())
        if operation["op"] == "add_entry":
            entry = normalize_entry(operation.get("entry", {}))
            if not entry["name"] or not entry["content"]:
                raise WorkshopError("新增条目必须包含名称和内容")
            operation["entry"] = entry
        elif operation["op"] in {"update_entry", "deactivate_entry", "request_delete", "delete_entry"}:
            _find_entry(self.draft, str(operation.get("entry_id", "")))
            if operation["op"] == "update_entry" and not isinstance(operation.get("changes"), dict):
                raise WorkshopError("修改条目必须提供 changes")
        elif operation["op"] == "update_overview":
            operation["overview"] = str(operation.get("overview", "")).strip()
        elif operation["op"] == "set_axioms":
            axioms = operation.get("axioms", [])
            if not isinstance(axioms, list):
                raise WorkshopError("世界公理必须是数组")
            operation["axioms"] = [str(item).strip() for item in axioms if str(item).strip()]
        return operation

    def apply_operations(self, operations: list[dict[str, Any]], *, confirm_high_risk: bool = False) -> dict[str, Any]:
        validated = [self._validate(item) for item in operations]
        applied, pending = [], []
        for operation in validated:
            if _is_high_risk(self.draft, operation) and not confirm_high_risk:
                self.pending.append(operation)
                pending.append(operation)
                continue
            if not applied:
                self._snapshot()
            self._apply(operation)
            applied.append(operation)
        if applied or pending:
            self.touch()
        return {"applied": applied, "pending": pending, "draft": copy.deepcopy(self.draft)}

    def _apply(self, operation: dict[str, Any]) -> None:
        op = operation["op"]
        if op == "update_overview":
            self.draft["overview"] = operation["overview"]
            return
        if op == "set_axioms":
            self.draft["axioms"] = normalize_axioms(operation["axioms"])
            return
        if op == "add_entry":
            entry = normalize_entry(operation["entry"])
            existing_ids = {item["id"] for item in self.draft.get("entries", [])}
            if entry["id"] in existing_ids:
                entry["id"] = f"entry_{uuid.uuid4().hex[:12]}"
            self.draft.setdefault("entries", []).append(entry)
            return
        index, current = _find_entry(self.draft, operation["entry_id"])
        if op == "update_entry":
            allowed = {"name", "keys", "content", "tags", "is_active"}
            changes = {key: value for key, value in operation["changes"].items() if key in allowed}
            updated = dict(current)
            updated.update(changes)
            updated["id"] = current["id"]
            self.draft["entries"][index] = normalize_entry(updated)
        elif op == "deactivate_entry":
            self.draft["entries"][index]["is_active"] = False
        elif op == "request_delete":
            tags = normalize_tags(current.get("tags", []))
            if "待删除" not in tags:
                tags.append("待删除")
            self.draft["entries"][index]["tags"] = tags
            self.draft["entries"][index]["is_active"] = False
        elif op == "delete_entry":
            self.draft["entries"].pop(index)

    def approve(self, operation_id: str) -> dict[str, Any]:
        for index, operation in enumerate(self.pending):
            if operation["operation_id"] == operation_id:
                self._snapshot()
                self._apply(operation)
                self.pending.pop(index)
                self.touch()
                return copy.deepcopy(self.draft)
        raise WorkshopError("待确认操作不存在")

    def reject(self, operation_id: str) -> None:
        before = len(self.pending)
        self.pending = [item for item in self.pending if item["operation_id"] != operation_id]
        if len(self.pending) == before:
            raise WorkshopError("待确认操作不存在")

    def undo(self) -> dict[str, Any]:
        if not self.snapshots:
            raise WorkshopError("没有可撤销的工坊修改")
        self.draft = self.snapshots.pop()
        self.touch()
        return copy.deepcopy(self.draft)

    def publish(self, output_path: Path | None = None) -> Path:
        path = Path(output_path or self.target_path)
        save_worldbook_atomic(path, self.draft)
        self.published = True
        self.dirty = False
        self.touch(dirty=False)
        return path

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target_path": str(self.target_path),
            "draft": self.draft,
            "snapshots": self.snapshots,
            "pending": self.pending,
            "messages": self.messages,
            "dirty": self.dirty,
            "published": self.published,
            "updated_at": self.updated_at,
        }

    def save_session(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.id}.json"
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldbookWorkshop":
        workshop = cls(str(data["id"]), Path(data["target_path"]), data.get("draft", {}))
        workshop.snapshots = data.get("snapshots", [])
        workshop.pending = data.get("pending", [])
        workshop.messages = data.get("messages", [])
        workshop.dirty = bool(data.get("dirty", False))
        workshop.published = bool(data.get("published", False))
        workshop.updated_at = str(data.get("updated_at") or workshop.updated_at)
        return workshop
