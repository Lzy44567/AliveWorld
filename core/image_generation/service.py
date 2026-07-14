"""Application service for provider-neutral image tasks."""

from __future__ import annotations

from typing import Any

from core.image_generation.models import ImageTask, ImageTaskStatus, TERMINAL_STATUSES
from core.image_generation.repository import ImageTaskRepository


class ImageTaskError(ValueError):
    pass


class ImageGenerationService:
    def __init__(self, repository: ImageTaskRepository):
        self.repository = repository

    def create(self, save_id: str, payload: dict[str, Any]) -> ImageTask:
        try:
            task = ImageTask.create(
                save_id=save_id,
                intent=str(payload.get("intent", "scene_cg")),
                provider_id=str(payload.get("provider_id", "comfyui")),
                workflow_id=str(payload.get("workflow_id", "builtin_basic")),
                prompt=payload.get("prompt"),
                source_message_id=str(payload.get("source_message_id", "")),
                character_ids=payload.get("character_ids"),
                context_snapshot=payload.get("context_snapshot"),
                provider_options=payload.get("provider_options"),
            )
        except (TypeError, ValueError) as exc:
            raise ImageTaskError(f"生图任务参数无效: {exc}") from exc
        return self.repository.save(task)

    def list(self) -> list[ImageTask]:
        return sorted(self.repository.list(), key=lambda item: item.created_at, reverse=True)

    def get(self, task_id: str) -> ImageTask:
        task = self.repository.get(task_id)
        if not task:
            raise ImageTaskError("生图任务不存在")
        return task

    def cancel(self, task_id: str) -> ImageTask:
        task = self.get(task_id)
        if task.status in TERMINAL_STATUSES:
            raise ImageTaskError("该任务已经结束，不能取消")
        task.status = ImageTaskStatus.CANCELLED
        task.progress = 0.0
        return self.repository.save(task)

    def retry(self, task_id: str) -> ImageTask:
        task = self.get(task_id)
        if task.status not in {ImageTaskStatus.FAILED, ImageTaskStatus.CANCELLED}:
            raise ImageTaskError("只有失败或已取消任务可以重试")
        task.status = ImageTaskStatus.READY if task.prompt.positive else ImageTaskStatus.QUEUED
        task.provider_job_id = ""
        task.progress = 0.0
        task.error_code = ""
        task.error_message = ""
        task.output_images = []
        return self.repository.save(task)
