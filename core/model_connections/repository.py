"""Private YAML persistence and legacy configuration migration."""

from __future__ import annotations

import copy
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

import yaml

from .models import (
    CONNECTION_SCHEMA_VERSION,
    TASK_SPECS,
    ConnectionProfile,
    ConnectionSnapshot,
    TaskRoute,
)


_PROFILE_NAMESPACE = uuid.UUID("9800bbf6-902e-4f29-a5e5-a96426c35c95")


def stable_profile_id(role: str) -> str:
    return str(uuid.uuid5(_PROFILE_NAMESPACE, f"aliveworld:{role}"))


MAIN_PROFILE_ID = stable_profile_id("main-text")
MEMORY_PROFILE_ID = stable_profile_id("memory-text")
PREFERENCE_PROFILE_ID = stable_profile_id("preference-text")
COMFYUI_PROFILE_ID = stable_profile_id("comfyui")


def _provider_hint(base_url: str) -> str:
    lowered = str(base_url or "").lower()
    for provider in ("deepseek", "openai", "google", "anthropic"):
        if provider in lowered:
            return provider
    if any(host in lowered for host in ("127.0.0.1", "localhost")):
        return "local"
    return "custom"


def _context_limit(value: Any) -> int:
    try:
        return max(8192, int(value or 32768))
    except (TypeError, ValueError):
        return 32768


class ConnectionRepository:
    """Owns model connection data while preserving unrelated system settings."""

    section_key = "model_connections"

    def __init__(self, config_path: str | Path):
        self.path = Path(config_path)

    def read_raw(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            return yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return {}

    def load(self, *, persist_migration: bool = False) -> ConnectionSnapshot:
        raw = self.read_raw()
        section = raw.get(self.section_key)
        if isinstance(section, dict) and isinstance(section.get("profiles"), dict):
            return self._decode(section)
        snapshot = self._from_legacy(raw)
        if persist_migration:
            self._backup_legacy(raw)
            self.save_snapshot(snapshot, base=raw)
        return snapshot

    def ensure_migrated(self) -> ConnectionSnapshot:
        return self.load(persist_migration=True)

    def save_snapshot(
        self,
        snapshot: ConnectionSnapshot,
        *,
        base: dict[str, Any] | None = None,
        sync_legacy: bool = True,
    ) -> None:
        raw = copy.deepcopy(base if base is not None else self.read_raw())
        raw[self.section_key] = snapshot.to_dict()
        if sync_legacy:
            self._sync_legacy_fields(raw, snapshot)
        self._atomic_write(raw)

    def update_legacy(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str,
        memory_api_key: str | None,
        memory_base_url: str,
        memory_model: str,
        preference_api_key: str | None,
        preference_base_url: str,
        preference_model: str,
        image_api_url: str | None,
        memory_context_limit: Any,
    ) -> ConnectionSnapshot:
        raw = self.read_raw()
        existing_section = raw.get(self.section_key)
        snapshot = (
            self._decode(existing_section)
            if isinstance(existing_section, dict) and isinstance(existing_section.get("profiles"), dict)
            else self._from_legacy(raw)
        )
        for value, key in (
            (api_key, "api_key"),
            (memory_api_key, "memory_api_key"),
            (preference_api_key, "preference_api_key"),
        ):
            if value is not None and str(value).strip():
                raw[key] = str(value).strip()
        raw.update(
            {
                "base_url": str(base_url or "").strip(),
                "model": str(model or "").strip(),
                "memory_base_url": str(memory_base_url or "").strip(),
                "memory_model": str(memory_model or "").strip(),
                "memory_context_limit": _context_limit(memory_context_limit),
                "preference_base_url": str(preference_base_url or "").strip(),
                "preference_model": str(preference_model or "").strip(),
            }
        )
        if image_api_url is not None:
            raw["image_api_url"] = str(image_api_url or "").strip()
        story = self.resolve(snapshot, "story")
        if story:
            story.profile.base_url = raw["base_url"]
            story.profile.default_model = raw["model"]
            if api_key is not None and str(api_key).strip():
                story.profile.api_key = str(api_key).strip()
        self._apply_optional_legacy_update(
            snapshot,
            raw,
            task="memory",
            profile_id=MEMORY_PROFILE_ID,
            name="记忆压缩接口",
            prefix="memory",
        )
        self._apply_optional_legacy_update(
            snapshot,
            raw,
            task="preference",
            profile_id=PREFERENCE_PROFILE_ID,
            name="偏好分析接口",
            prefix="preference",
        )
        image = self.resolve(snapshot, "image_generation")
        if image and image_api_url is not None and raw.get("image_api_url"):
            image.profile.base_url = raw["image_api_url"].rstrip("/")
        self._validate_snapshot(snapshot)
        self.save_snapshot(snapshot, base=raw)
        return snapshot

    def legacy_public_config(self) -> dict[str, Any]:
        snapshot = self.ensure_migrated()
        raw = self.read_raw()
        story = self.resolve(snapshot, "story")
        memory = self.resolve(snapshot, "memory")
        preference = self.resolve(snapshot, "preference")
        image = self.resolve(snapshot, "image_generation")
        return {
            "apiKey": "",
            "apiKeyConfigured": bool(story and story.profile.api_key),
            "apiReady": bool(
                story
                and story.profile.enabled
                and story.profile.base_url
                and story.model
            ),
            "apiBaseUrl": story.profile.base_url if story else "",
            "model": story.model if story else "",
            "memoryApiKey": "",
            "memoryApiKeyConfigured": bool(
                memory and story and memory.profile.id != story.profile.id and memory.profile.api_key
            ),
            "memoryApiBaseUrl": (
                memory.profile.base_url if memory and story and memory.profile.id != story.profile.id else ""
            ),
            "memoryModel": (
                memory.model
                if memory and story and memory.profile.id != story.profile.id
                else self._route_model_override(snapshot, "memory")
            ),
            "memoryContextLimit": _context_limit(raw.get("memory_context_limit", 32768)),
            "preferenceApiKey": "",
            "preferenceApiKeyConfigured": bool(
                preference and story and preference.profile.id != story.profile.id and preference.profile.api_key
            ),
            "preferenceApiBaseUrl": (
                preference.profile.base_url
                if preference and story and preference.profile.id != story.profile.id
                else ""
            ),
            "preferenceModel": (
                preference.model
                if preference and story and preference.profile.id != story.profile.id
                else self._route_model_override(snapshot, "preference")
            ),
            "imageApiUrl": image.profile.base_url if image else "http://127.0.0.1:8188",
        }

    def create_profile(self, data: dict[str, Any]) -> ConnectionProfile:
        snapshot = self.ensure_migrated()
        self._ensure_unique_name(snapshot, str(data.get("name") or ""))
        profile_id = str(uuid.uuid4())
        profile = ConnectionProfile.from_dict(profile_id, data)
        snapshot.profiles[profile_id] = profile
        self._validate_snapshot(snapshot)
        self.save_snapshot(snapshot)
        return profile

    def update_profile(
        self,
        profile_id: str,
        data: dict[str, Any],
        *,
        api_key: str | None = None,
        clear_api_key: bool = False,
    ) -> ConnectionProfile:
        snapshot = self.ensure_migrated()
        current = snapshot.profiles.get(profile_id)
        if not current:
            raise KeyError(profile_id)
        name = str(data.get("name", current.name) or "").strip()
        self._ensure_unique_name(snapshot, name, except_id=profile_id)
        merged = current.to_dict()
        merged.update({key: value for key, value in data.items() if key != "api_key"})
        if clear_api_key:
            merged["api_key"] = ""
        elif api_key is not None and str(api_key).strip():
            merged["api_key"] = str(api_key).strip()
        updated = ConnectionProfile.from_dict(profile_id, merged)
        snapshot.profiles[profile_id] = updated
        self._validate_snapshot(snapshot)
        self.save_snapshot(snapshot)
        return updated

    def clone_profile(self, profile_id: str, name: str) -> ConnectionProfile:
        snapshot = self.ensure_migrated()
        source = snapshot.profiles.get(profile_id)
        if not source:
            raise KeyError(profile_id)
        self._ensure_unique_name(snapshot, name)
        clone_id = str(uuid.uuid4())
        data = source.to_dict()
        data["name"] = str(name or "").strip()
        data["last_test"] = {}
        clone = ConnectionProfile.from_dict(clone_id, data)
        snapshot.profiles[clone_id] = clone
        self.save_snapshot(snapshot)
        return clone

    def set_profile_enabled(self, profile_id: str, enabled: bool) -> ConnectionProfile:
        snapshot = self.ensure_migrated()
        profile = snapshot.profiles.get(profile_id)
        if not profile:
            raise KeyError(profile_id)
        profile.enabled = bool(enabled)
        self.save_snapshot(snapshot)
        return profile

    def delete_profile(self, profile_id: str) -> None:
        snapshot = self.ensure_migrated()
        profile = snapshot.profiles.get(profile_id)
        if not profile:
            raise KeyError(profile_id)
        used_by = [
            TASK_SPECS[task]["label"]
            for task, route in snapshot.routes.items()
            if route.connection_id == profile_id and task in TASK_SPECS
        ]
        if used_by:
            raise ValueError(f"接口“{profile.name}”仍用于：{'、'.join(used_by)}；请先重新分配")
        snapshot.profiles.pop(profile_id)
        self.save_snapshot(snapshot)

    def set_route(self, task: str, route: TaskRoute) -> TaskRoute:
        if task not in TASK_SPECS:
            raise ValueError(f"未知功能用途：{task}")
        if task in {"story", "image_generation"} and not route.connection_id:
            raise ValueError(f"{TASK_SPECS[task]['label']} 必须直接选择一个接口")
        snapshot = self.ensure_migrated()
        snapshot.routes[task] = route
        self._validate_snapshot(snapshot)
        self.save_snapshot(snapshot)
        return route

    def reveal_profile_secret(self, profile_id: str) -> str:
        profile = self.ensure_migrated().profiles.get(profile_id)
        if not profile:
            raise KeyError(profile_id)
        return profile.api_key

    def record_test(self, profile_id: str, result: dict[str, Any]) -> ConnectionProfile:
        snapshot = self.ensure_migrated()
        profile = snapshot.profiles.get(profile_id)
        if not profile:
            raise KeyError(profile_id)
        profile.last_test = dict(result or {})
        self.save_snapshot(snapshot)
        return profile

    def reveal_legacy_secret(self, field: str) -> str:
        snapshot = self.ensure_migrated()
        task_map = {
            "apiKey": "story",
            "memoryApiKey": "memory",
            "preferenceApiKey": "preference",
        }
        task = task_map.get(field)
        if not task:
            raise KeyError(field)
        resolved = self.resolve(snapshot, task)
        story = self.resolve(snapshot, "story")
        if task != "story" and resolved and story and resolved.profile.id == story.profile.id:
            return ""
        return resolved.profile.api_key if resolved else ""

    def resolve(self, snapshot: ConnectionSnapshot, task: str):
        from .router import resolve_connection

        return resolve_connection(snapshot, task)

    def _decode(self, section: dict[str, Any]) -> ConnectionSnapshot:
        profiles = {
            profile_id: ConnectionProfile.from_dict(profile_id, data)
            for profile_id, data in (section.get("profiles") or {}).items()
            if isinstance(data, dict)
        }
        routes = self._default_routes()
        for task, data in (section.get("routes") or {}).items():
            if task in TASK_SPECS and isinstance(data, dict):
                routes[task] = TaskRoute.from_dict(data)
        return ConnectionSnapshot(
            profiles=profiles,
            routes=routes,
            schema_version=int(section.get("schema_version") or CONNECTION_SCHEMA_VERSION),
        )

    def _validate_snapshot(self, snapshot: ConnectionSnapshot) -> None:
        for task in TASK_SPECS:
            self.resolve(snapshot, task)

    @staticmethod
    def _ensure_unique_name(
        snapshot: ConnectionSnapshot,
        name: str,
        *,
        except_id: str = "",
    ) -> None:
        normalized = str(name or "").strip().casefold()
        if not normalized:
            raise ValueError("接口配置名称不能为空")
        if any(
            profile_id != except_id and profile.name.casefold() == normalized
            for profile_id, profile in snapshot.profiles.items()
        ):
            raise ValueError(f"已存在同名接口“{str(name).strip()}”")

    def _from_legacy(self, raw: dict[str, Any]) -> ConnectionSnapshot:
        main_base = str(raw.get("base_url") or "https://api.deepseek.com").strip()
        main_model = str(raw.get("model") or "deepseek-v4-flash").strip()
        main_key = str(raw.get("api_key") or "").strip()
        profiles = {
            MAIN_PROFILE_ID: ConnectionProfile(
                id=MAIN_PROFILE_ID,
                name="主文本接口",
                category="text",
                protocol="openai_compatible",
                provider_hint=_provider_hint(main_base),
                base_url=main_base,
                api_key=main_key,
                default_model=main_model,
            )
        }
        routes = self._default_routes()
        routes["story"] = TaskRoute(connection_id=MAIN_PROFILE_ID)

        self._legacy_task_profile(
            profiles,
            routes,
            raw,
            task="memory",
            profile_id=MEMORY_PROFILE_ID,
            name="记忆压缩接口",
            prefix="memory",
            main_profile=profiles[MAIN_PROFILE_ID],
        )
        self._legacy_task_profile(
            profiles,
            routes,
            raw,
            task="preference",
            profile_id=PREFERENCE_PROFILE_ID,
            name="偏好分析接口",
            prefix="preference",
            main_profile=profiles[MAIN_PROFILE_ID],
        )

        image_url = str(raw.get("image_api_url") or "http://127.0.0.1:8188").strip()
        profiles[COMFYUI_PROFILE_ID] = ConnectionProfile(
            id=COMFYUI_PROFILE_ID,
            name="本地 ComfyUI",
            category="image",
            protocol="comfyui",
            provider_hint="comfyui",
            base_url=image_url,
        )
        routes["image_generation"] = TaskRoute(connection_id=COMFYUI_PROFILE_ID)
        return ConnectionSnapshot(profiles=profiles, routes=routes)

    @staticmethod
    def _default_routes() -> dict[str, TaskRoute]:
        return {
            task: TaskRoute(inherit_from=spec["inherit_from"])
            for task, spec in TASK_SPECS.items()
        }

    @staticmethod
    def _legacy_task_profile(
        profiles: dict[str, ConnectionProfile],
        routes: dict[str, TaskRoute],
        raw: dict[str, Any],
        *,
        task: str,
        profile_id: str,
        name: str,
        prefix: str,
        main_profile: ConnectionProfile,
    ) -> None:
        api_key = str(raw.get(f"{prefix}_api_key") or "").strip()
        base_url = str(raw.get(f"{prefix}_base_url") or "").strip()
        model = str(raw.get(f"{prefix}_model") or "").strip()
        if api_key or base_url:
            resolved_base = base_url or main_profile.base_url
            profiles[profile_id] = ConnectionProfile(
                id=profile_id,
                name=name,
                category="text",
                protocol="openai_compatible",
                provider_hint=_provider_hint(resolved_base),
                base_url=resolved_base,
                api_key=api_key or main_profile.api_key,
                default_model=model or main_profile.default_model,
            )
            routes[task] = TaskRoute(connection_id=profile_id)
        else:
            routes[task] = TaskRoute(inherit_from="story", model_override=model)

    def _apply_optional_legacy_update(
        self,
        snapshot: ConnectionSnapshot,
        raw: dict[str, Any],
        *,
        task: str,
        profile_id: str,
        name: str,
        prefix: str,
    ) -> None:
        api_key = str(raw.get(f"{prefix}_api_key") or "").strip()
        base_url = str(raw.get(f"{prefix}_base_url") or "").strip()
        model = str(raw.get(f"{prefix}_model") or "").strip()
        current_route = snapshot.routes.get(task, TaskRoute(inherit_from="story"))
        if api_key or base_url:
            current = (
                snapshot.profiles.get(current_route.connection_id)
                if current_route.connection_id
                else None
            )
            story = self.resolve(snapshot, "story")
            if not current:
                current = ConnectionProfile(
                    id=profile_id,
                    name=name,
                    category="text",
                    protocol="openai_compatible",
                    provider_hint=_provider_hint(base_url or (story.profile.base_url if story else "")),
                    base_url=base_url or (story.profile.base_url if story else ""),
                    api_key=api_key or (story.profile.api_key if story else ""),
                    default_model=model or (story.model if story else ""),
                )
                snapshot.profiles[current.id] = current
            else:
                current.base_url = (base_url or current.base_url).rstrip("/")
                current.default_model = model or current.default_model
                if api_key:
                    current.api_key = api_key
            snapshot.routes[task] = TaskRoute(connection_id=current.id)
        else:
            snapshot.routes[task] = TaskRoute(inherit_from="story", model_override=model)

    @staticmethod
    def _route_model_override(snapshot: ConnectionSnapshot, task: str) -> str:
        route = snapshot.routes.get(task)
        return route.model_override if route else ""

    def _backup_legacy(self, raw: dict[str, Any]) -> None:
        if not raw or self.section_key in raw or not self.path.is_file():
            return
        backup = self.path.with_name(f"{self.path.stem}.pre-model-connections.yml")
        if not backup.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.path, backup)

    def _sync_legacy_fields(self, raw: dict[str, Any], snapshot: ConnectionSnapshot) -> None:
        story = self.resolve(snapshot, "story")
        memory = self.resolve(snapshot, "memory")
        preference = self.resolve(snapshot, "preference")
        image = self.resolve(snapshot, "image_generation")
        if story:
            raw.update(
                {
                    "api_key": story.profile.api_key,
                    "base_url": story.profile.base_url,
                    "model": story.model,
                }
            )
        self._sync_optional_legacy(raw, snapshot, "memory", memory, story)
        self._sync_optional_legacy(raw, snapshot, "preference", preference, story)
        if image:
            raw["image_api_url"] = image.profile.base_url

    @staticmethod
    def _sync_optional_legacy(
        raw: dict[str, Any],
        snapshot: ConnectionSnapshot,
        prefix: str,
        resolved,
        story,
    ) -> None:
        route = snapshot.routes.get(prefix, TaskRoute(inherit_from="story"))
        separate = bool(resolved and story and resolved.profile.id != story.profile.id)
        raw[f"{prefix}_api_key"] = resolved.profile.api_key if separate else ""
        raw[f"{prefix}_base_url"] = resolved.profile.base_url if separate else ""
        raw[f"{prefix}_model"] = (
            resolved.model if separate else route.model_override
        )

    def _atomic_write(self, raw: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                yaml.safe_dump(raw, stream, allow_unicode=True, sort_keys=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
