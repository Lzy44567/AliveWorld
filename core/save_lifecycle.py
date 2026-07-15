"""Atomic clone and rename operations for story save directories."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from core.asset_lifecycle import AssetLifecycleError, normalize_asset_name


def save_directory_name(save_name: str) -> str:
    name = normalize_asset_name(save_name)
    safe = "".join(char for char in name if char.isalnum() or char in " _-").strip().rstrip(".")
    if not safe:
        raise AssetLifecycleError("存档名无法转换为安全目录名")
    return f"Save_{safe}"


def _read_state(save_dir: Path) -> dict:
    state_path = save_dir / "session_state.json"
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssetLifecycleError(f"存档状态无法读取：{exc}") from exc
    if not isinstance(data, dict):
        raise AssetLifecycleError("存档状态格式无效")
    return data


def _write_state(save_dir: Path, data: dict) -> None:
    state_path = save_dir / "session_state.json"
    temp = state_path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, state_path)


def _target(root: Path, new_name: str) -> tuple[str, Path]:
    name = normalize_asset_name(new_name)
    target = root / save_directory_name(name)
    if target.exists():
        raise AssetLifecycleError(f"已存在同名存档“{name}”")
    return name, target


def clone_save(source_dir: str | Path, new_name: str) -> Path:
    source = Path(source_dir)
    if not source.is_dir():
        raise AssetLifecycleError("源存档不存在")
    name, target = _target(source.parent, new_name)
    temp = target.with_name(target.name + ".copying")
    if temp.exists():
        raise AssetLifecycleError("目标存档正在创建，请稍后重试")
    try:
        shutil.copytree(source, temp)
        state = _read_state(temp)
        state["save_name"] = name
        state["save_dir_path"] = str(target)
        _write_state(temp, state)
        os.replace(temp, target)
    except Exception:
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)
        raise
    return target


def rename_save(source_dir: str | Path, new_name: str) -> Path:
    source = Path(source_dir)
    if not source.is_dir():
        raise AssetLifecycleError("源存档不存在")
    current = _read_state(source)
    name = normalize_asset_name(new_name)
    if str(current.get("save_name", "")).strip() == name:
        raise AssetLifecycleError("新名称与原名称相同")
    _, target = _target(source.parent, name)
    os.replace(source, target)
    try:
        current["save_name"] = name
        current["save_dir_path"] = str(target)
        _write_state(target, current)
    except Exception:
        os.replace(target, source)
        raise
    return target
