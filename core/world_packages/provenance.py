"""Structured provenance for installed packages and story-local asset instances."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

import yaml


def package_system_tags(package_name: str, author: str, package_id: str) -> list[str]:
    """Return immutable, display-only origin tags for package management UI."""
    short_id = str(package_id).removeprefix("awpkg_")[:8]
    return [f"来源：{package_name}", f"作者：{author}", f"包标识：{short_id}"]


def annotate_story_asset(
    source: Path,
    destination: Path,
    *,
    package_id: str,
    package_version: str,
    package_name: str,
    source_asset_id: str,
) -> str:
    """Copy an asset while attaching immutable origin metadata when YAML permits it."""
    local_instance_id = f"awlocal_{uuid.uuid4().hex}"
    if source.suffix.casefold() not in {".yml", ".yaml"}:
        destination.write_bytes(source.read_bytes())
        return local_instance_id
    try:
        data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError, UnicodeDecodeError):
        destination.write_bytes(source.read_bytes())
        return local_instance_id
    if not isinstance(data, dict):
        destination.write_bytes(source.read_bytes())
        return local_instance_id
    metadata = data.setdefault("_aliveworld", {})
    if not isinstance(metadata, dict):
        metadata = {}
        data["_aliveworld"] = metadata
    metadata["asset_id"] = source_asset_id
    metadata["local_instance_id"] = local_instance_id
    metadata["origin"] = {
        "package_id": package_id,
        "package_version": package_version,
        "package_name": package_name,
        "source_asset_id": source_asset_id,
    }
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    os.replace(temporary, destination)
    return local_instance_id


def story_origin(save_dir: str | Path) -> dict[str, Any] | None:
    path = Path(save_dir) / "world_package.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def related_stories(saves_root: str | Path, package_id: str, version: str | None = None) -> list[dict[str, str]]:
    """Find stories created from a package without inferring ownership from names."""
    root = Path(saves_root)
    if not root.is_dir():
        return []
    stories: list[dict[str, str]] = []
    for save_dir in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda item: item.name.casefold()):
        origin = story_origin(save_dir)
        if not origin or origin.get("package_id") != package_id:
            continue
        if version is not None and str(origin.get("version", "")) != version:
            continue
        save_name = save_dir.name.removeprefix("Save_")
        state_path = save_dir / "session_state.json"
        try:
            state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            state = {}
        if isinstance(state, dict) and str(state.get("save_name", "")).strip():
            save_name = str(state["save_name"]).strip()
        stories.append({"save_name": save_name, "path": str(save_dir), "package_version": str(origin.get("version", ""))})
    return stories


def system_tags_from_asset(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []
    metadata = data.get("_aliveworld")
    origin = metadata.get("origin") if isinstance(metadata, dict) else None
    if not isinstance(origin, dict) or not origin.get("package_id"):
        return []
    short_id = str(origin["package_id"]).removeprefix("awpkg_")[:8]
    labels = [f"来源：{origin.get('package_name') or '世界包'}"]
    if origin.get("package_version"):
        labels.append(f"包版本：{origin['package_version']}")
    labels.append(f"包标识：{short_id}")
    return labels


def refresh_local_instance_id(data: Any) -> str | None:
    """Give a copied package-derived asset its own local instance identity."""
    if not isinstance(data, dict):
        return None
    metadata = data.get("_aliveworld")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("origin"), dict):
        return None
    identifier = f"awlocal_{uuid.uuid4().hex}"
    metadata["local_instance_id"] = identifier
    return identifier
