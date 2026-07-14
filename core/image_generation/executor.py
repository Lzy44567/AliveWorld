"""Background execution of persistent image tasks."""

from __future__ import annotations

import threading
from collections.abc import Callable

from core.image_generation.models import ImageTask, ImageTaskStatus, TERMINAL_STATUSES
from core.image_generation.providers.base import ImageProvider
from core.image_generation.service import ImageGenerationService, ImageTaskError


ProviderFactory = Callable[[ImageTask], ImageProvider]
CompletionHandler = Callable[[ImageTask], None]


class ImageTaskRunner:
    def __init__(self, service: ImageGenerationService, provider_factory: ProviderFactory, *, poll_interval: float = 1.0, completion_handler: CompletionHandler | None = None):
        self.service = service
        self.provider_factory = provider_factory
        self.poll_interval = poll_interval
        self.completion_handler = completion_handler
        self._threads: dict[str, threading.Thread] = {}
        self._providers: dict[str, ImageProvider] = {}
        self._lock = threading.RLock()

    def start(self, task_id: str) -> bool:
        task = self.service.get(task_id)
        if task.status not in {ImageTaskStatus.READY, ImageTaskStatus.SUBMITTED, ImageTaskStatus.RUNNING}:
            return False
        with self._lock:
            thread = self._threads.get(task_id)
            if thread and thread.is_alive():
                return False
            thread = threading.Thread(target=self._run, args=(task_id,), name=f"image-task-{task_id}", daemon=True)
            self._threads[task_id] = thread
            thread.start()
        return True

    def recover(self) -> int:
        count = 0
        for task in self.service.list():
            if task.status in {ImageTaskStatus.SUBMITTED, ImageTaskStatus.RUNNING} and task.provider_job_id:
                count += int(self.start(task.id))
        return count

    def cancel(self, task_id: str) -> ImageTask:
        task = self.service.cancel(task_id)
        with self._lock:
            provider = self._providers.get(task_id)
        if provider and task.provider_job_id:
            try:
                provider.cancel(task.provider_job_id)
            except Exception:
                pass
        return task

    def _run(self, task_id: str) -> None:
        provider = None
        try:
            task = self.service.get(task_id)
            provider = self.provider_factory(task)
            with self._lock:
                self._providers[task_id] = provider
            if not task.provider_job_id:
                job = provider.submit(task)
                task = self.service.mark_submitted(task_id, job.id)
            while True:
                latest = self.service.get(task_id)
                if latest.status == ImageTaskStatus.CANCELLED:
                    if latest.provider_job_id:
                        provider.cancel(latest.provider_job_id)
                    return
                job = provider.query(latest.provider_job_id)
                latest = self.service.apply_provider_job(task_id, job)
                if latest.status in TERMINAL_STATUSES:
                    if latest.status == ImageTaskStatus.SUCCEEDED and self.completion_handler:
                        self.completion_handler(latest)
                    return
                threading.Event().wait(self.poll_interval)
        except (ImageTaskError, Exception) as exc:
            try:
                self.service.fail(task_id, "provider_error", str(exc))
            except Exception:
                pass
        finally:
            with self._lock:
                self._providers.pop(task_id, None)
                self._threads.pop(task_id, None)
