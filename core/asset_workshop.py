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
from core.character_profiles import CharacterProfileError, coordinate_character_write
from core.character_asset_write import character_revision, character_write_guard, read_character
from utils.atomic_yaml import save_yaml_atomic


ASSET_FIELDS = {
    "characters": {"name", "tags", "description", "starting_scene", "is_player", "portrait", "role_fields"},
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
        if result.get('role_fields') is not None:
            try:
                result = coordinate_character_write({}, result)
            except CharacterProfileError as exc:
                raise AssetWorkshopError(str(exc)) from None
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
        if asset_type == 'characters':
            self.source_revision = character_revision(source)
        self.publication_intent = None
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

    def assert_editable(self) -> None:
        if self.publication_intent:
            raise AssetWorkshopError('上次发布结果待核对，请重新载入工坊')
        if self.published:
            raise AssetWorkshopError("这轮工坊已经发布，请开启新一轮后再修改")

    def ai_fields(self, draft=None):
        draft = self.draft if draft is None else draft
        return {'tags', 'role_fields'} if self.asset_type == 'characters' and draft.get('role_fields') is not None else AI_FIELDS[self.asset_type]

    def _validate(self, raw: Any, *, actor: str, draft=None) -> dict[str, Any]:
        draft = self.draft if draft is None else draft
        if not isinstance(raw, dict) or raw.get("op") != "update_fields":
            raise AssetWorkshopError("资产工坊拒绝了未授权操作")
        changes = raw.get("changes")
        if not isinstance(changes, dict):
            raise AssetWorkshopError("资产工坊修改必须提供 changes")
        allowed = self.ai_fields(draft) if actor == "ai" else ASSET_FIELDS[self.asset_type] - {"name", "portrait", "influence_refs"}
        unknown = set(changes) - allowed
        if unknown:
            raise AssetWorkshopError(f"这些字段不能由工坊修改：{', '.join(sorted(unknown))}")
        if actor == 'ai' and 'role_fields' in changes and changes['role_fields'] is None:
            raise AssetWorkshopError('AI不能将独立角色字段转为自由文本')
        try:
            merged = normalize_asset(self.asset_type, coordinate_character_write(draft, changes) if self.asset_type == 'characters' else {**draft, **changes})
        except CharacterProfileError as exc:
            raise AssetWorkshopError(str(exc)) from None
        clean_changes = {key: merged.get(key) for key in changes}
        return {
            "op": "update_fields",
            "operation_id": str(raw.get("operation_id") or uuid4()),
            "changes": clean_changes,
            "reason": str(raw.get("reason", "")).strip()[:500],
        }

    def propose_operations(self, operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.assert_editable()
        self.proposed = [self._validate(item, actor="ai") for item in operations]
        if self.proposed:
            self.touch()
        return deepcopy(self.proposed)

    def clear_proposal(self) -> None:
        self.proposed = []

    def review_operations(self, source, operation_ids, accept):
        from core.workshop_review import select_operations
        self.assert_editable()
        if source != 'proposed':
            raise AssetWorkshopError('未知的审阅列表')
        selected = select_operations(self.proposed, operation_ids, AssetWorkshopError)
        if accept:
            self.apply_operations(selected, actor='ai')
        ids = set(operation_ids)
        self.proposed = [item for item in self.proposed if item['operation_id'] not in ids]
        self.touch()

    def apply_operations(self, operations: list[dict[str, Any]], *, actor: str = "player") -> dict[str, Any]:
        self.assert_editable()
        candidate = deepcopy(self.draft)
        validated = []
        for raw in operations:
            operation = self._validate(raw, actor=actor, draft=candidate)
            validated.append(operation)
            candidate = normalize_asset(self.asset_type, coordinate_character_write(candidate, operation['changes']) if self.asset_type == 'characters' else {**candidate, **operation['changes']})
        if candidate != self.draft:
            self.snapshots.append({"draft": deepcopy(self.draft), "operations": deepcopy(self.operations)})
            self.snapshots = self.snapshots[-50:]
            self.draft = candidate
            self.operations.extend(validated)
            self.touch()
        return {"applied": validated, "draft": deepcopy(self.draft)}

    def undo(self) -> None:
        self.assert_editable()
        if not self.snapshots:
            raise AssetWorkshopError("没有可撤销的工坊修改")
        snapshot = self.snapshots.pop()
        self.draft = snapshot["draft"]
        self.operations = snapshot["operations"]
        self.touch()

    def _finish_publication(self, revision=None):
        self.base = deepcopy(self.draft)
        self.source_revision = revision or asset_revision(self.base)
        self.operations = []; self.proposed = []; self.snapshots = []
        self.dirty = False; self.published = True; self.publication_intent = None
        self.touch(dirty=False)

    def recover_publication(self, directory):
        if not self.publication_intent:
            return
        with character_write_guard(self.target_path):
            candidate = deepcopy(self)
            current = read_character(self.target_path)
            revision = character_revision(current)
            if str(self.target_path.resolve()) != self.publication_intent['target_path']:
                raise AssetWorkshopError('发布目标已变化，保留草稿，请核对资产')
            if revision == self.publication_intent['output_hash']:
                candidate._finish_publication(revision)
            elif revision == self.publication_intent['base_revision']:
                candidate.publication_intent = None
            else:
                raise AssetWorkshopError('发布恢复冲突，目标已被修改；未重写资产')
            candidate.save_session(directory)
            self.__dict__.clear(); self.__dict__.update(candidate.__dict__)

    def publish(self, directory=None) -> Path:
        self.assert_editable()
        if "模板" in self.draft.get("tags", []) or self.target_path.name.endswith(".template.yml"):
            raise AssetWorkshopError("模板资产不能直接发布，请先克隆为个人资产")
        if self.asset_type == 'characters':
            with character_write_guard(self.target_path):
                current = read_character(self.target_path)
                if not current or character_revision(current) != self.source_revision:
                    raise AssetWorkshopError('原角色卡已更新，请重新进入工坊；未覆盖新内容')
                output = coordinate_character_write(current, self.draft)
                intent = {'target_path': str(self.target_path.resolve()), 'base_revision': self.source_revision, 'output_hash': character_revision(output)}
                self.publication_intent = intent
                try:
                    if directory is not None:
                        self.save_session(directory)
                except Exception:
                    self.publication_intent = None
                    raise
                pending_state = deepcopy(self.__dict__)
                save_yaml_atomic(self.target_path, output)
                self._finish_publication(intent['output_hash'])
                if directory is not None:
                    try:
                        self.save_session(directory)
                    except Exception:
                        self.__dict__.clear(); self.__dict__.update(pending_state)
                        raise
                return self.target_path
        current = yaml.safe_load(self.target_path.read_text(encoding="utf-8")) or {}
        if asset_revision(normalize_asset(self.asset_type, current)) != self.source_revision:
            raise AssetWorkshopError("原资产已在其他位置发生变化，请关闭工坊后重新进入，避免覆盖新内容")
        # Preserve runtime/media fields that the workshop does not own.
        output = {**current, **self.draft}
        save_yaml_atomic(self.target_path, output)
        self._finish_publication()
        return self.target_path

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "asset_type": self.asset_type, "target_path": str(self.target_path),
            "base": self.base, "draft": self.draft, "source_revision": self.source_revision,
            "operations": self.operations, "proposed": self.proposed, "snapshots": self.snapshots,
            "messages": self.messages, "suggested_actions": self.suggested_actions,
            "dirty": self.dirty, "published": self.published, "updated_at": self.updated_at,
            "publication_intent": self.publication_intent,
            "revision_kind": "raw-character-v1" if self.asset_type == 'characters' else "normalized-v1",
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
        # Upgrade older normalized revisions only against an unchanged target.
        if workshop.asset_type == 'characters' and not data.get('revision_kind') and not data.get('publication_intent'):
            with character_write_guard(workshop.target_path):
                current = read_character(workshop.target_path)
                if current and asset_revision(normalize_asset('characters', current)) == workshop.source_revision:
                    workshop.source_revision = character_revision(current)
        workshop.dirty = bool(data.get("dirty", False))
        workshop.published = bool(data.get("published", False))
        workshop.publication_intent = deepcopy(data.get('publication_intent'))
        workshop.updated_at = str(data.get("updated_at") or workshop.updated_at)
        return workshop
