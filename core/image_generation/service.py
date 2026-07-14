"""Application service for provider-neutral image tasks."""

from __future__ import annotations

from typing import Any
from pathlib import Path

from core.image_generation.models import ImageTask, ImageTaskStatus, TERMINAL_STATUSES
from core.image_generation.providers.base import ProviderJob
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

    def regenerate(self, task_id: str) -> ImageTask:
        source = self.get(task_id)
        payload = source.to_dict()
        return self.create(source.save_id, payload)

    def mark_compiling(self, task_id: str) -> ImageTask:
        task = self.get(task_id)
        if task.status != ImageTaskStatus.QUEUED:
            raise ImageTaskError("只有等待提示词的任务可以开始整理")
        task.status = ImageTaskStatus.COMPILING_PROMPT
        return self.repository.save(task)

    def apply_compiled_prompt(self, task_id: str, result: dict[str, Any]) -> ImageTask:
        task = self.get(task_id)
        if task.status == ImageTaskStatus.CANCELLED:
            return task
        positive = str(result.get("positive", "")).strip()
        if not positive:
            raise ImageTaskError("AI 没有返回可用的正面提示词")
        task.prompt.positive = positive
        if str(result.get("negative", "")).strip():
            task.prompt.negative = str(result["negative"]).strip()
        task.context_snapshot["prompt_compiler"] = {
            "content_focus": str(result.get("content_focus", "general")),
            "notes": str(result.get("notes", "")),
        }
        task.status = ImageTaskStatus.READY
        return self.repository.save(task)

    def delete(self, task_id: str) -> None:
        task = self.get(task_id)
        if task.status not in TERMINAL_STATUSES:
            raise ImageTaskError("请先取消正在运行的任务，再删除")
        for item in task.output_images:
            path = self.repository.outputs_dir / Path(item).name
            if path.is_file():
                path.unlink()
        self.repository.remove(task_id)

    def mark_submitted(self, task_id: str, provider_job_id: str) -> ImageTask:
        task = self.get(task_id)
        task.status = ImageTaskStatus.SUBMITTED
        task.provider_job_id = str(provider_job_id)
        return self.repository.save(task)

    def apply_provider_job(self, task_id: str, job: ProviderJob) -> ImageTask:
        task = self.get(task_id)
        if task.status == ImageTaskStatus.CANCELLED:
            return task
        states = {
            "submitted": ImageTaskStatus.SUBMITTED,
            "running": ImageTaskStatus.RUNNING,
            "succeeded": ImageTaskStatus.SUCCEEDED,
            "failed": ImageTaskStatus.FAILED,
        }
        task.status = states.get(job.state, ImageTaskStatus.RUNNING)
        task.progress = max(0.0, min(1.0, float(job.progress or 0.0)))
        task.output_images = list(job.output_images)
        task.error_code = str(job.error_code or "")
        task.error_message = str(job.error_message or "")
        return self.repository.save(task)

    def fail(self, task_id: str, code: str, message: str) -> ImageTask:
        task = self.get(task_id)
        if task.status != ImageTaskStatus.CANCELLED:
            task.status = ImageTaskStatus.FAILED
            task.error_code = str(code)
            task.error_message = str(message)
        return self.repository.save(task)
