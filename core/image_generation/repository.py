"""Atomic per-save persistence for image generation tasks."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from core.image_generation.models import ImageTask


class ImageTaskRepository:
    def __init__(self, save_dir: str | Path):
        self.root = Path(save_dir) / "images"
        self.outputs_dir = self.root / "generated"
        self.references_dir = self.root / "references"
        self.path = self.root / "tasks.json"
        self._lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.references_dir.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[ImageTask]:
        with self._lock:
            return list(self._read().values())

    def get(self, task_id: str) -> ImageTask | None:
        with self._lock:
            return self._read().get(task_id)

    def save(self, task: ImageTask) -> ImageTask:
        with self._lock:
            tasks = self._read()
            task.touch()
            tasks[task.id] = task
            self._write(tasks)
            return task

    def remove(self, task_id: str) -> ImageTask | None:
        with self._lock:
            tasks = self._read()
            task = tasks.pop(task_id, None)
            if task is not None:
                self._write(tasks)
            return task

    def _read(self) -> dict[str, ImageTask]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"生图任务文件无法读取: {exc}") from exc
        items = raw.get("tasks", []) if isinstance(raw, dict) else []
        tasks: dict[str, ImageTask] = {}
        for item in items:
            if isinstance(item, dict) and item.get("id"):
                task = ImageTask.from_dict(item)
                tasks[task.id] = task
        return tasks

    def _write(self, tasks: dict[str, ImageTask]) -> None:
        payload = {"version": 1, "tasks": [task.to_dict() for task in tasks.values()]}
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, self.path)
