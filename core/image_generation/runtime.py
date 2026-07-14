"""Per-save image runtime registry."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from core.image_generation.executor import ImageTaskRunner
from core.image_generation.models import ImageTask
from core.image_generation.providers.comfyui import ComfyUIProvider
from core.image_generation.repository import ImageTaskRepository
from core.image_generation.service import ImageGenerationService
from core.image_generation.workflows import WorkflowRepository
from core.image_generation.pipeline import ImageGenerationPipeline
from core.image_generation.portrait import PortraitAssignmentError, assign_current_portrait, assign_global_portrait


@dataclass
class ImageRuntime:
    service: ImageGenerationService
    runner: ImageTaskRunner
    pipeline: ImageGenerationPipeline


_runtimes: dict[str, ImageRuntime] = {}
_lock = threading.RLock()


def get_image_runtime(save_dir: str | Path) -> ImageRuntime:
    key = str(Path(save_dir).resolve())
    with _lock:
        existing = _runtimes.get(key)
        if existing:
            return existing
        repository = ImageTaskRepository(save_dir)
        service = ImageGenerationService(repository)

        def provider_factory(task: ImageTask):
            if task.provider_id != "comfyui":
                raise ValueError(f"尚未实现生图服务商: {task.provider_id}")
            base_url = str(task.provider_options.get("base_url", "http://127.0.0.1:8188"))
            return ComfyUIProvider(
                base_url,
                workflows=WorkflowRepository(),
                output_dir=repository.outputs_dir,
                timeout=float(task.provider_options.get("timeout", 10.0) or 10.0),
            )

        def completion_handler(task: ImageTask) -> None:
            if task.intent.value != "character_portrait" or not task.context_snapshot.get("auto_assign_portrait") or task.context_snapshot.get("portrait_assignment"):
                return
            character_name = str(task.context_snapshot.get("character_name", "")).strip()
            try:
                scope = str(task.context_snapshot.get("portrait_scope", "local"))
                if scope == "global":
                    assign_global_portrait(character_name, task, service.repository.outputs_dir, 0)
                else:
                    assign_current_portrait(save_dir, character_name, task, 0)
                task.context_snapshot["portrait_assignment"] = {"status": "success", "scope": scope, "character_name": character_name}
            except PortraitAssignmentError as exc:
                task.context_snapshot["portrait_assignment"] = {"status": "failed", "message": str(exc)}
            service.repository.save(task)

        runner = ImageTaskRunner(service, provider_factory, completion_handler=completion_handler)
        runtime = ImageRuntime(service=service, runner=runner, pipeline=ImageGenerationPipeline(service, runner))
        _runtimes[key] = runtime
        runner.recover()
        return runtime


def clear_image_runtimes() -> None:
    """Test helper; running daemon threads are not forcefully terminated."""
    with _lock:
        _runtimes.clear()
