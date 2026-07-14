"""Provider protocol kept independent from FastAPI and story prompts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from core.image_generation.models import ImageTask


@dataclass
class ProviderCapabilities:
    provider_id: str
    connected: bool
    supports_cancel: bool = False
    supports_progress: bool = False
    workflows: list[str] = field(default_factory=list)
    checkpoints: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class ProviderJob:
    id: str
    state: str
    progress: float = 0.0
    output_images: list[str] = field(default_factory=list)
    error_code: str = ""
    error_message: str = ""


class ImageProvider(Protocol):
    id: str

    def check(self) -> ProviderCapabilities: ...
    def submit(self, task: ImageTask) -> ProviderJob: ...
    def query(self, provider_job_id: str) -> ProviderJob: ...
    def cancel(self, provider_job_id: str) -> bool: ...
