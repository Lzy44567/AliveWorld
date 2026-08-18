"""Stable identities embedded in editable YAML assets."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import yaml

from core.world_packages.models import PackageFormatError, new_asset_id, validate_identifier


METADATA_KEY = "_aliveworld"


def asset_id_from_data(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    metadata = data.get(METADATA_KEY)
    if not isinstance(metadata, dict) or not metadata.get("asset_id"):
        return None
    try:
        return validate_identifier(metadata["asset_id"], prefix="awasset")
    except PackageFormatError:
        return None


def assign_new_asset_id(data: dict[str, Any]) -> str:
    metadata = data.get(METADATA_KEY)
    metadata = dict(metadata) if isinstance(metadata, dict) else {}
    identifier = new_asset_id()
    metadata["asset_id"] = identifier
    data[METADATA_KEY] = metadata
    return identifier


def ensure_yaml_asset_id(path: str | Path) -> str:
    target = Path(path)
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise PackageFormatError(f"无法读取资产：{target.name}") from exc
    if not isinstance(data, dict):
        raise PackageFormatError(f"资产不是有效对象：{target.name}")
    existing = asset_id_from_data(data)
    if existing:
        return existing
    identifier = assign_new_asset_id(data)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    os.replace(temporary, target)
    return identifier
