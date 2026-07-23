"""Transactional drafts for character, style, and undercurrent entity workshops."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml


ASSET_FIELDS = {
    "characters": {"name", "tags", "description", "starting_scene", "is_player", "portrait"},
    "styles": {"name", "tags", "content"},
    "entities": {
        "name", "tags", "description", "motive", "status", "mechanisms", "plans",
        "recent_actions", "triggers", "relationships", "importance", "is_active",
        "influence_refs",
    },
}
AI_FIELDS = {
    "characters": {"tags", "description", "starting_scene"},
    "styles": {"tags", "content"},
    "entities": {
        "tags", "description", "motive", "status", "mechanisms", "plans",
        "recent_actions", "triggers", "relationships", "importance",
    },
}


class AssetWorkshopError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def asset_revision(asset: dict[str, Any]) -> str:
    encoded = json.dumps(asset, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_asset(asset_type: str, raw: dict[str, Any]) -> dict[str, Any]:
    if asset_type not in ASSET_FIELDS:
        raise AssetWorkshopError("该资产类型尚未接入工坊")
    source = deepcopy(raw if isinstance(raw, dict) else {})
    result = {key: deepcopy(value) for key, value in source.items() if key in ASSET_FIELDS[asset_type]}
    result["name"] = str(result.get("name", "")).strip()
    tags = result.get("tags", [])
    if isinstance(tags, str):
        tags = tags.replace("，", ",").split(",")
    result["tags"] = list(dict.fromkeys(str(item).strip() for item in (tags or []) if str(item).strip()))
    if asset_type == "characters":
        result["description"] = str(result.get("description", "")).strip()
        result["starting_scene"] = str(result.get("starting_scene", "")).strip()
        result["is_player"] = bool(result.get("is_player", False))
    elif asset_type == "styles":
        result["content"] = str(result.get("content", "")).strip()
    else:
        for key in ("description", "motive", "status"):
            result[key] = str(result.get(key, "")).strip()
        for key in ("mechanisms", "plans", "recent_actions"):
            value = result.get(key, [])
            if isinstance(value, str):
                value = value.splitlines()
            result[key] = [str(item).strip() for item in (value or []) if str(item).strip()]
        result["triggers"] = [
            {"condition": str(item.get("condition", "")).strip(), "result": str(item.get("result", "")).strip()}
            for item in (result.get("triggers", []) or []) if isinstance(item, dict)
            and (str(item.get("condition", "")).strip() or str(item.get("result", "")).strip())
        ]
        result["relationships"] = [
            {"target": str(item.get("target", "")).strip(), "relation": str(item.get("relation", "")).strip()}
            for item in (result.get("relationships", []) or []) if isinstance(item, dict)
            and (str(item.get("target", "")).strip() or str(item.get("relation", "")).strip())
        ]
        try:
            result["importance"] = min(1.0, max(0.0, float(result.get("importance", 0.5))))
        except (TypeError, ValueError):
            result["importance"] = 0.5
        result["is_active"] = bool(result.get("is_active", True))
    return result


class AssetWorkshop:
    def __init__(self, workshop_id: str, asset_type: str, target_path: Path, source: dict[str, Any]):
        self.id = workshop_id
        self.asset_type = asset_type
        self.target_path = Path(target_path)
        self.base = normalize_asset(asset_type, source)
        self.draft = deepcopy(self.base)
        self.source_revision = asset_revision(self.base)
        self.operations: list[dict[str, Any]] = []
        self.proposed: list[dict[str, Any]] = []
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

    def _validate(self, raw: Any, *, actor: str) -> dict[str, Any]:
        if not isinstance(raw, dict) or raw.get("op") != "update_fields":
            raise AssetWorkshopError("资产工坊拒绝了未授权操作")
        changes = raw.get("changes")
        if not isinstance(changes, dict):
            raise AssetWorkshopError("资产工坊修改必须提供 changes")
        allowed = AI_FIELDS[self.asset_type] if actor == "ai" else ASSET_FIELDS[self.asset_type] - {"name", "portrait", "influence_refs"}
        unknown = set(changes) - allowed
        if unknown:
            raise AssetWorkshopError(f"这些字段不能由工坊修改：{', '.join(sorted(unknown))}")
        merged = normalize_asset(self.asset_type, {**self.draft, **changes})
        clean_changes = {key: merged.get(key) for key in changes}
        return {
            "op": "update_fields",
            "operation_id": str(raw.get("operation_id") or uuid4()),
            "changes": clean_changes,
            "reason": str(raw.get("reason", "")).strip()[:500],
        }

    def propose_operations(self, operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.proposed = [self._validate(item, actor="ai") for item in operations]
        if self.proposed:
            self.touch()
        return deepcopy(self.proposed)

    def clear_proposal(self) -> None:
        self.proposed = []

    def apply_operations(self, operations: list[dict[str, Any]], *, actor: str = "player") -> dict[str, Any]:
        validated = [self._validate(item, actor=actor) for item in operations]
        for operation in validated:
            updated = normalize_asset(self.asset_type, {**self.draft, **operation["changes"]})
            if updated == self.draft:
                continue
            self.snapshots.append({"draft": deepcopy(self.draft), "operations": deepcopy(self.operations)})
            self.snapshots = self.snapshots[-50:]
            self.draft = updated
            self.operations.append(operation)
            self.touch()
        return {"applied": validated, "draft": deepcopy(self.draft)}

    def undo(self) -> None:
        if not self.snapshots:
            raise AssetWorkshopError("没有可撤销的工坊修改")
        snapshot = self.snapshots.pop()
        self.draft = snapshot["draft"]
        self.operations = snapshot["operations"]
        self.touch()

    def publish(self) -> Path:
        if "模板" in self.draft.get("tags", []) or self.target_path.name.endswith(".template.yml"):
            raise AssetWorkshopError("模板资产不能直接发布，请先克隆为个人资产")
        current = yaml.safe_load(self.target_path.read_text(encoding="utf-8")) or {}
        if asset_revision(normalize_asset(self.asset_type, current)) != self.source_revision:
            raise AssetWorkshopError("原资产已在其他位置发生变化，请关闭工坊后重新进入，避免覆盖新内容")
        # Preserve runtime/media fields that the workshop does not own.
        output = {**current, **self.draft}
        temp = self.target_path.with_suffix(self.target_path.suffix + ".tmp")
        temp.write_text(yaml.safe_dump(output, allow_unicode=True, sort_keys=False), encoding="utf-8")
        temp.replace(self.target_path)
        self.base = deepcopy(self.draft)
        self.source_revision = asset_revision(self.base)
        self.operations = []
        self.proposed = []
        self.snapshots = []
        self.dirty = False
        self.published = True
        self.touch(dirty=False)
        return self.target_path

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "asset_type": self.asset_type, "target_path": str(self.target_path),
            "base": self.base, "draft": self.draft, "source_revision": self.source_revision,
            "operations": self.operations, "proposed": self.proposed, "snapshots": self.snapshots,
            "messages": self.messages, "suggested_actions": self.suggested_actions,
            "dirty": self.dirty, "published": self.published, "updated_at": self.updated_at,
        }

    def save_session(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.id}.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetWorkshop":
        workshop = cls(
            str(data["id"]), str(data["asset_type"]), Path(data["target_path"]),
            data.get("base", data.get("draft", {})),
        )
        for key in ("draft", "operations", "proposed", "snapshots", "messages", "suggested_actions"):
            setattr(workshop, key, deepcopy(data.get(key, getattr(workshop, key))))
        workshop.source_revision = str(data.get("source_revision") or workshop.source_revision)
        workshop.dirty = bool(data.get("dirty", False))
        workshop.published = bool(data.get("published", False))
        workshop.updated_at = str(data.get("updated_at") or workshop.updated_at)
        return workshop
