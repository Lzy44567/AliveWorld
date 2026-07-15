"""Safe rename/clone operations shared by global and per-save YAML assets."""

from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Any

import yaml

from core.worldbook import normalize_worldbook, save_worldbook_atomic


class AssetLifecycleError(ValueError):
    pass


def normalize_asset_name(value: Any) -> str:
    name = " ".join(str(value or "").split()).strip()
    if not name:
        raise AssetLifecycleError("名称不能为空")
    if len(name) > 80:
        raise AssetLifecycleError("名称不能超过 80 个字符")
    if any(char in name for char in '<>:"/\\|?*') or name in {".", ".."}:
        raise AssetLifecycleError("名称包含文件系统不支持的字符")
    return name


def filename_for_asset(name: str) -> str:
    safe = re.sub(r"[^\w\s-]", "", normalize_asset_name(name), flags=re.UNICODE).strip().rstrip(".")
    if not safe:
        raise AssetLifecycleError("名称无法转换为安全文件名")
    return f"{safe}.yml"


def _load(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise AssetLifecycleError(f"资产文件无法读取：{exc}") from exc
    if not isinstance(data, dict):
        raise AssetLifecycleError("资产内容不是有效对象")
    return data


def _is_template(path: Path, data: dict[str, Any]) -> bool:
    tags = data.get("tags", []) if isinstance(data.get("tags", []), list) else []
    return path.name.endswith(".template.yml") or data.get("is_template") is True or "模板" in tags


def find_yaml_asset(directory: str | Path, name: str) -> Path | None:
    target = normalize_asset_name(name).casefold()
    root = Path(directory)
    if not root.exists():
        return None
    matches = []
    for path in root.glob("*.yml"):
        try:
            data = _load(path)
        except AssetLifecycleError:
            continue
        if str(data.get("name", "")).strip().casefold() == target:
            matches.append((bool(_is_template(path, data)), path))
    matches.sort(key=lambda item: item[0])
    return matches[0][1] if matches else None


def _write(path: Path, data: dict[str, Any], *, worldbook: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if worldbook:
        save_worldbook_atomic(path, normalize_worldbook(data))
        return
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    os.replace(temp, path)


def clone_yaml_asset(
    directory: str | Path,
    source_name: str,
    new_name: str,
    *,
    worldbook: bool = False,
    source_path: str | Path | None = None,
) -> Path:
    root = Path(directory)
    source = Path(source_path) if source_path else find_yaml_asset(root, source_name)
    if not source:
        raise AssetLifecycleError("源资产不存在")
    if not source.exists():
        raise AssetLifecycleError("源资产不存在")
    new_name = normalize_asset_name(new_name)
    if find_yaml_asset(root, new_name):
        raise AssetLifecycleError(f"已存在同名资产“{new_name}”")
    target = root / filename_for_asset(new_name)
    if target.exists():
        raise AssetLifecycleError("目标文件名已被占用")
    data = copy.deepcopy(_load(source))
    data["name"] = new_name
    data.pop("is_template", None)
    if isinstance(data.get("tags"), list):
        data["tags"] = [tag for tag in data["tags"] if tag != "模板"]
    _write(target, data, worldbook=worldbook)
    return target


def rename_yaml_asset(directory: str | Path, source_name: str, new_name: str, *, worldbook: bool = False) -> Path:
    root = Path(directory)
    source = find_yaml_asset(root, source_name)
    if not source:
        raise AssetLifecycleError("源资产不存在")
    data = _load(source)
    if _is_template(source, data):
        raise AssetLifecycleError("模板资产不能重命名，请先克隆为个人资产")
    new_name = normalize_asset_name(new_name)
    if source_name.strip().casefold() == new_name.casefold():
        if source_name.strip() == new_name:
            raise AssetLifecycleError("新名称与原名称相同")
    conflict = find_yaml_asset(root, new_name)
    if conflict and conflict.resolve() != source.resolve():
        raise AssetLifecycleError(f"已存在同名资产“{new_name}”")
    target = root / filename_for_asset(new_name)
    if target.exists() and target.resolve() != source.resolve():
        raise AssetLifecycleError("目标文件名已被占用")
    data["name"] = new_name
    _write(target, data, worldbook=worldbook)
    if target.resolve() != source.resolve():
        source.unlink()
    return target
