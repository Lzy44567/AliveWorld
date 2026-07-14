"""Assign generated images to local character cards."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

from core.image_generation.models import ImageIntent, ImageTask, ImageTaskStatus


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
