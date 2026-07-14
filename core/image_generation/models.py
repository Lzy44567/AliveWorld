"""Provider-neutral image generation task models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ImageIntent(str, Enum):
    CHARACTER_PORTRAIT = "character_portrait"
    CHARACTER_CG = "character_cg"
    SCENE_CG = "scene_cg"


class ImageTaskStatus(str, Enum):
    QUEUED = "queued"
    COMPILING_PROMPT = "compiling_prompt"
    READY = "ready"
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = {
    ImageTaskStatus.SUCCEEDED,
    ImageTaskStatus.FAILED,
    ImageTaskStatus.CANCELLED,
}


@dataclass
class ImageReference:
    path: str
    role: str = "character"
    label: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageReference":
        return cls(
            path=str(data.get("path", "")).strip(),
            role=str(data.get("role", "character")).strip() or "character",
            label=str(data.get("label", "")).strip(),
        )


@dataclass
class ImagePromptSpec:
    positive: str = ""
    negative: str = ""
    style_preference: str = ""
    presentation_level: str = ""
    width: int = 512
    height: int = 768
    count: int = 1
    steps: int = 20
    cfg: float = 7.0
    seed: int | None = None
    references: list[ImageReference] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ImagePromptSpec":
        data = data if isinstance(data, dict) else {}
        references = [
            ImageReference.from_dict(item)
            for item in data.get("references", [])
            if isinstance(item, dict) and str(item.get("path", "")).strip()
        ]
        seed = data.get("seed")
        return cls(
            positive=str(data.get("positive", "")).strip(),
            negative=str(data.get("negative", "")).strip(),
            style_preference=str(data.get("style_preference", "")).strip(),
            presentation_level=str(data.get("presentation_level", "")).strip(),
            width=max(64, min(4096, int(data.get("width", 512) or 512))) // 8 * 8,
            height=max(64, min(4096, int(data.get("height", 768) or 768))) // 8 * 8,
            count=max(1, min(4, int(data.get("count", 1) or 1))),
            steps=max(1, min(100, int(data.get("steps", 20) or 20))),
            cfg=max(1.0, min(30.0, float(data.get("cfg", 7.0) or 7.0))),
            seed=int(seed) if seed is not None and str(seed).strip() else None,
            references=references,
        )


@dataclass
class ImageTask:
    id: str
    save_id: str
    intent: ImageIntent
    status: ImageTaskStatus
    provider_id: str
    workflow_id: str
    prompt: ImagePromptSpec
    source_message_id: str = ""
    character_ids: list[str] = field(default_factory=list)
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    provider_options: dict[str, Any] = field(default_factory=dict)
    provider_job_id: str = ""
    progress: float = 0.0
    error_code: str = ""
    error_message: str = ""
    output_images: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def create(
        cls,
        *,
        save_id: str,
        intent: str,
        provider_id: str,
        workflow_id: str,
        prompt: dict[str, Any] | None = None,
        source_message_id: str = "",
        character_ids: list[str] | None = None,
        context_snapshot: dict[str, Any] | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> "ImageTask":
        parsed_prompt = ImagePromptSpec.from_dict(prompt)
        status = ImageTaskStatus.READY if parsed_prompt.positive else ImageTaskStatus.QUEUED
        return cls(
            id=f"image_{uuid4().hex[:12]}",
            save_id=str(save_id),
            intent=ImageIntent(intent),
            status=status,
            provider_id=str(provider_id or "comfyui"),
            workflow_id=str(workflow_id or "builtin_basic"),
            prompt=parsed_prompt,
            source_message_id=str(source_message_id or ""),
            character_ids=[str(item) for item in (character_ids or []) if str(item).strip()],
            context_snapshot=dict(context_snapshot or {}),
            provider_options=dict(provider_options or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageTask":
        return cls(
            id=str(data["id"]),
            save_id=str(data.get("save_id", "")),
            intent=ImageIntent(data.get("intent", ImageIntent.SCENE_CG.value)),
            status=ImageTaskStatus(data.get("status", ImageTaskStatus.QUEUED.value)),
            provider_id=str(data.get("provider_id", "comfyui")),
            workflow_id=str(data.get("workflow_id", "builtin_basic")),
            prompt=ImagePromptSpec.from_dict(data.get("prompt")),
            source_message_id=str(data.get("source_message_id", "")),
            character_ids=[str(item) for item in data.get("character_ids", [])],
            context_snapshot=dict(data.get("context_snapshot", {})),
            provider_options=dict(data.get("provider_options", {})),
            provider_job_id=str(data.get("provider_job_id", "")),
            progress=max(0.0, min(1.0, float(data.get("progress", 0.0) or 0.0))),
            error_code=str(data.get("error_code", "")),
            error_message=str(data.get("error_message", "")),
            output_images=[str(item) for item in data.get("output_images", [])],
            created_at=str(data.get("created_at", utc_now())),
            updated_at=str(data.get("updated_at", utc_now())),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["intent"] = self.intent.value
        data["status"] = self.status.value
        return data

    def touch(self) -> None:
        self.updated_at = utc_now()
