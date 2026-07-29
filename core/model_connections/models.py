"""Domain objects for provider connections and AliveWorld task routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


CONNECTION_SCHEMA_VERSION = 1

TASK_SPECS: dict[str, dict[str, str]] = {
    "story": {"category": "text", "label": "故事正文", "inherit_from": ""},
    "overseer": {"category": "text", "label": "暗流 Overseer", "inherit_from": "story"},
    "workshop": {"category": "text", "label": "工坊 AI", "inherit_from": "story"},
    "worldbook_capture": {"category": "text", "label": "世界书捕获", "inherit_from": "story"},
    "memory": {"category": "text", "label": "记忆压缩", "inherit_from": "story"},
    "preference": {"category": "text", "label": "用户偏好分析", "inherit_from": "story"},
    "image_prompt": {"category": "text", "label": "生图提示词整理", "inherit_from": "story"},
    "image_generation": {"category": "image", "label": "图片生成", "inherit_from": ""},
}

SUPPORTED_PROTOCOLS = {"openai_compatible", "comfyui"}
SUPPORTED_CATEGORIES = {"text", "image"}


def _text(value: Any) -> str:
    return str(value or "").strip()


@dataclass(slots=True)
class ConnectionProfile:
    id: str
    name: str
    category: str
    protocol: str
    base_url: str = ""
    api_key: str = ""
    default_model: str = ""
    provider_hint: str = "custom"
    enabled: bool = True
    advanced_options: dict[str, Any] = field(default_factory=dict)
    last_test: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.id = _text(self.id)
        self.name = _text(self.name)
        self.category = _text(self.category)
        self.protocol = _text(self.protocol)
        self.base_url = _text(self.base_url).rstrip("/")
        self.api_key = _text(self.api_key)
        self.default_model = _text(self.default_model)
        self.provider_hint = _text(self.provider_hint) or "custom"
        self.advanced_options = dict(self.advanced_options or {})
        self.last_test = dict(self.last_test or {})
        if not self.id:
            raise ValueError("接口配置缺少稳定 ID")
        if not self.name:
            raise ValueError("接口配置名称不能为空")
        if self.category not in SUPPORTED_CATEGORIES:
            raise ValueError(f"暂不支持接口类别：{self.category}")
        if self.protocol not in SUPPORTED_PROTOCOLS:
            raise ValueError(f"暂不支持接口协议：{self.protocol}")
        if self.category == "text" and self.protocol != "openai_compatible":
            raise ValueError("文本接口首版只支持 OpenAI-compatible 协议")
        if self.category == "image" and self.protocol != "comfyui":
            raise ValueError("生图接口首版只支持 ComfyUI 协议")

    @classmethod
    def from_dict(cls, profile_id: str, data: dict[str, Any]) -> "ConnectionProfile":
        return cls(
            id=profile_id,
            name=data.get("name", ""),
            category=data.get("category", ""),
            protocol=data.get("protocol", ""),
            base_url=data.get("base_url", ""),
            api_key=data.get("api_key", ""),
            default_model=data.get("default_model", ""),
            provider_hint=data.get("provider_hint", "custom"),
            enabled=bool(data.get("enabled", True)),
            advanced_options=data.get("advanced_options") or {},
            last_test=data.get("last_test") or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "protocol": self.protocol,
            "provider_hint": self.provider_hint,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "default_model": self.default_model,
            "enabled": self.enabled,
            "advanced_options": dict(self.advanced_options),
            "last_test": dict(self.last_test),
        }

    def public_dict(self) -> dict[str, Any]:
        data = self.to_dict()
        data.pop("api_key", None)
        data.update({"id": self.id, "api_key_configured": bool(self.api_key)})
        return data


@dataclass(slots=True)
class TaskRoute:
    connection_id: str = ""
    inherit_from: str = ""
    model_override: str = ""

    def __post_init__(self) -> None:
        self.connection_id = _text(self.connection_id)
        self.inherit_from = _text(self.inherit_from)
        self.model_override = _text(self.model_override)
        if self.connection_id and self.inherit_from:
            raise ValueError("功能用途不能同时指定接口和继承来源")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TaskRoute":
        data = data or {}
        return cls(
            connection_id=data.get("connection_id", ""),
            inherit_from=data.get("inherit_from", ""),
            model_override=data.get("model_override", ""),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "connection_id": self.connection_id,
            "inherit_from": self.inherit_from,
            "model_override": self.model_override,
        }


@dataclass(slots=True)
class ConnectionSnapshot:
    profiles: dict[str, ConnectionProfile]
    routes: dict[str, TaskRoute]
    schema_version: int = CONNECTION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profiles": {profile_id: profile.to_dict() for profile_id, profile in self.profiles.items()},
            "routes": {task: route.to_dict() for task, route in self.routes.items()},
        }

    def public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profiles": [profile.public_dict() for profile in self.profiles.values()],
            "routes": {
                task: {
                    **route.to_dict(),
                    "label": TASK_SPECS[task]["label"],
                    "category": TASK_SPECS[task]["category"],
                }
                for task, route in self.routes.items()
                if task in TASK_SPECS
            },
        }


@dataclass(frozen=True, slots=True)
class ResolvedConnection:
    task: str
    profile: ConnectionProfile
    model: str = ""

    def ai_config(self) -> dict[str, str]:
        if self.profile.category != "text":
            raise ValueError(f"{self.task} 不是文本模型用途")
        return {
            "api_key": self.profile.api_key or ("not-required" if self.profile.base_url else ""),
            "base_url": self.profile.base_url,
            "model": self.model or self.profile.default_model,
        }
