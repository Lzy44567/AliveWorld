"""Background prompt compilation followed by provider execution."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from core.image_generation.executor import ImageTaskRunner
from core.image_generation.service import ImageGenerationService


class ImageGenerationPipeline:
    def __init__(self, service: ImageGenerationService, runner: ImageTaskRunner):
        self.service = service
        self.runner = runner

    def compile_and_start(self, task_id: str, compile_prompt: Callable[[], dict[str, Any]]) -> None:
        self.service.mark_compiling(task_id)
        thread = threading.Thread(
            target=self._compile_and_start,
            args=(task_id, compile_prompt),
            name=f"image-prompt-{task_id}",
            daemon=True,
        )
        thread.start()

    def _compile_and_start(self, task_id: str, compile_prompt: Callable[[], dict[str, Any]]) -> None:
        try:
            self.service.apply_compiled_prompt(task_id, compile_prompt())
            self.runner.start(task_id)
        except Exception as exc:
            self.service.fail(task_id, "prompt_compilation_error", str(exc))
