"""Assign generated images to local character cards."""

from __future__ import annotations

import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

from core.image_generation.models import ImageIntent, ImageTask, ImageTaskStatus
from utils.file_io import CHAR_DIR


class PortraitAssignmentError(ValueError):
    pass


def assign_current_portrait(save_dir: str | Path, character_name: str, task: ImageTask, image_index: int = 0) -> dict:
    if task.intent != ImageIntent.CHARACTER_PORTRAIT:
        raise PortraitAssignmentError("只有角色立绘任务可以设为当前立绘")
    if task.status != ImageTaskStatus.SUCCEEDED or not task.output_images:
        raise PortraitAssignmentError("立绘任务尚未成功完成")
    if image_index < 0 or image_index >= len(task.output_images):
        raise PortraitAssignmentError("立绘图片不存在")
    if task.character_ids and character_name not in task.character_ids:
        raise PortraitAssignmentError("该立绘不属于指定角色")

    directory = Path(save_dir) / "characters"
    for path in directory.glob("*.yml") if directory.exists() else []:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if str(data.get("name", path.stem)) != character_name:
            continue
        data["portrait"] = {
            "task_id": task.id,
            "image_index": image_index,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        temp = path.with_suffix(".tmp")
        temp.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        os.replace(temp, path)
        return data
    raise PortraitAssignmentError("本局角色卡不存在，请先将角色载入本局")


def assign_global_portrait(character_name: str, task: ImageTask, source_dir: str | Path, image_index: int = 0) -> dict:
    _validate_assignment(character_name, task, image_index)
    directory = Path(CHAR_DIR)
    target_card = _find_character_card(directory, character_name)
    if target_card is None:
        raise PortraitAssignmentError("全局角色卡不存在")
    data = yaml.safe_load(target_card.read_text(encoding="utf-8")) or {}
    source = Path(source_dir) / Path(task.output_images[image_index]).name
    if not source.is_file():
        raise PortraitAssignmentError("立绘原图不存在")
    portraits = directory / "_portraits"
    portraits.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w.-]+", "_", character_name, flags=re.UNICODE).strip("_") or "character"
    filename = f"{safe_name}_{task.id}_{image_index}{source.suffix.lower()}"
    shutil.copy2(source, portraits / filename)
    data["portrait"] = {
        "scope": "global",
        "path": filename,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    temp = target_card.with_suffix(".tmp")
    temp.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    os.replace(temp, target_card)
    return data


def task_is_local_portrait(save_dir: str | Path, task_id: str) -> bool:
    directory = Path(save_dir) / "characters"
    for path in directory.glob("*.yml") if directory.exists() else []:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if str((data.get("portrait") or {}).get("task_id", "")) == task_id:
            return True
    return False


def global_portrait_path(filename: str) -> Path:
    root = (Path(CHAR_DIR) / "_portraits").resolve()
    path = (root / Path(filename).name).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PortraitAssignmentError("全局立绘路径无效") from exc
    if not path.is_file():
        raise PortraitAssignmentError("全局立绘不存在")
    return path


def _validate_assignment(character_name: str, task: ImageTask, image_index: int) -> None:
    if task.intent != ImageIntent.CHARACTER_PORTRAIT:
        raise PortraitAssignmentError("只有角色立绘任务可以设为当前立绘")
    if task.status != ImageTaskStatus.SUCCEEDED or not task.output_images:
        raise PortraitAssignmentError("立绘任务尚未成功完成")
    if image_index < 0 or image_index >= len(task.output_images):
        raise PortraitAssignmentError("立绘图片不存在")
    if task.character_ids and character_name not in task.character_ids:
        raise PortraitAssignmentError("该立绘不属于指定角色")


def _find_character_card(directory: Path, character_name: str) -> Path | None:
    for path in directory.glob("*.yml") if directory.exists() else []:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if str(data.get("name", path.stem)) == character_name:
            return path
    return None
