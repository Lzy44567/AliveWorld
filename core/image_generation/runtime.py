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


@dataclass
class ImageRuntime:
    service: ImageGenerationService
    runner: ImageTaskRunner


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

        runner = ImageTaskRunner(service, provider_factory)
        runtime = ImageRuntime(service=service, runner=runner)
        _runtimes[key] = runtime
        runner.recover()
        return runtime


def clear_image_runtimes() -> None:
    """Test helper; running daemon threads are not forcefully terminated."""
    with _lock:
        _runtimes.clear()
