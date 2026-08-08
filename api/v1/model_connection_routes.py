"""API for private model connection profiles and feature routing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.ai_engine import AIEngine
from core.image_generation.providers.comfyui import ComfyUIProvider
from core.model_connections.discovery import ModelDiscoveryService
from core.model_connections.models import TASK_SPECS, TaskRoute
from core.model_connections.repository import ConnectionRepository
from utils.runtime_paths import PATHS


router = APIRouter()
repository = ConnectionRepository(PATHS.config_file)
model_discovery = ModelDiscoveryService()


class ProfilePayload(BaseModel):
    name: str
    category: str
    protocol: str
    providerHint: str = "custom"
    baseUrl: str = ""
    apiKey: Optional[str] = None
    defaultModel: str = ""
    enabled: bool = True
    advancedOptions: dict[str, Any] = Field(default_factory=dict)
    clearApiKey: bool = False


class ClonePayload(BaseModel):
    name: str


class RoutePayload(BaseModel):
    connectionId: str = ""
    inheritFrom: str = ""
    modelOverride: str = ""


class EnabledPayload(BaseModel):
    enabled: bool


def _profile_data(payload: ProfilePayload) -> dict[str, Any]:
    return {
        "name": payload.name,
        "category": payload.category,
        "protocol": payload.protocol,
        "provider_hint": payload.providerHint,
        "base_url": payload.baseUrl,
        "api_key": str(payload.apiKey or "").strip(),
        "default_model": payload.defaultModel,
        "enabled": payload.enabled,
        "advanced_options": payload.advancedOptions,
    }


def _refresh_runtime() -> None:
    # Local import avoids making the domain repository depend on FastAPI routes.
    from api.v1.game_routes import reload_system_config_runtime

    reload_system_config_runtime()


def _error(exc: Exception, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail=str(exc))


@router.get("")
def list_connections():
    return repository.ensure_migrated().public_dict()


@router.post("/profiles")
def create_profile(payload: ProfilePayload):
    try:
        profile = repository.create_profile(_profile_data(payload))
        _refresh_runtime()
        return profile.public_dict()
    except ValueError as exc:
        raise _error(exc)


@router.post("/profiles/{profile_id}")
def update_profile(profile_id: str, payload: ProfilePayload):
    try:
        profile = repository.update_profile(
            profile_id,
            _profile_data(payload),
            api_key=payload.apiKey,
            clear_api_key=payload.clearApiKey,
        )
        model_discovery.invalidate(profile_id)
        _refresh_runtime()
        return profile.public_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail="接口配置不存在")
    except ValueError as exc:
        raise _error(exc)


@router.post("/profiles/{profile_id}/enabled")
def set_profile_enabled(profile_id: str, payload: EnabledPayload):
    try:
        profile = repository.set_profile_enabled(profile_id, payload.enabled)
        _refresh_runtime()
        return profile.public_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail="接口配置不存在")


@router.get("/profiles/{profile_id}/models")
def discover_profile_models(profile_id: str, refresh: bool = False):
    profile = repository.ensure_migrated().profiles.get(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="接口配置不存在")
    return model_discovery.discover(profile, refresh=refresh).public_dict()


@router.post("/profiles/{profile_id}/clone")
def clone_profile(profile_id: str, payload: ClonePayload):
    try:
        profile = repository.clone_profile(profile_id, payload.name)
        _refresh_runtime()
        return profile.public_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail="接口配置不存在")
    except ValueError as exc:
        raise _error(exc)


@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: str):
    try:
        repository.delete_profile(profile_id)
        _refresh_runtime()
        return {"status": "success"}
    except KeyError:
        raise HTTPException(status_code=404, detail="接口配置不存在")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/profiles/{profile_id}/reveal-secret")
def reveal_profile_secret(profile_id: str):
    try:
        return {"value": repository.reveal_profile_secret(profile_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="接口配置不存在")


@router.post("/profiles/{profile_id}/test")
def test_profile(profile_id: str):
    snapshot = repository.ensure_migrated()
    profile = snapshot.profiles.get(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="接口配置不存在")
    tested_at = datetime.now(timezone.utc).isoformat()
    result: dict[str, Any]
    if profile.category == "text":
        missing = []
        if not profile.base_url:
            missing.append("接口地址")
        if not profile.default_model:
            missing.append("默认模型")
        if missing:
            raise HTTPException(status_code=400, detail=f"请先填写：{'、'.join(missing)}")
        engine = AIEngine(
            {
                "api_key": profile.api_key or "not-required",
                "base_url": profile.base_url,
                "model": profile.default_model,
            }
        )
        content, error = engine.chat_text(
            "你是 API 连通性测试助手。",
            "只回复“连接成功”四个字。",
            temp=0,
            trace_label=f"接口测试:{profile.name}",
        )
        result = {
            "ok": not bool(error),
            "tested_at": tested_at,
            "message": str(error or "模型连接正常")[:300],
            "model": profile.default_model,
            "response": content.strip()[:50] if not error else "",
        }
    else:
        capabilities = ComfyUIProvider(profile.base_url).check()
        result = {
            "ok": bool(capabilities.connected),
            "tested_at": tested_at,
            "message": capabilities.message,
            "models": list(capabilities.checkpoints),
        }
    repository.record_test(profile_id, result)
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result["message"])
    return result


@router.post("/routes/{task}")
def update_route(task: str, payload: RoutePayload):
    if task not in TASK_SPECS:
        raise HTTPException(status_code=404, detail="功能用途不存在")
    try:
        route = repository.set_route(
            task,
            TaskRoute(
                connection_id=payload.connectionId,
                inherit_from=payload.inheritFrom,
                model_override=payload.modelOverride,
            ),
        )
        _refresh_runtime()
        return {
            **route.to_dict(),
            "task": task,
            "label": TASK_SPECS[task]["label"],
        }
    except ValueError as exc:
        raise _error(exc)
