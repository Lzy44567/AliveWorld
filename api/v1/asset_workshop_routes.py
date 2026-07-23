"""Character, style, and undercurrent entity workshop API."""

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import yaml

from core.asset_workshop import AssetWorkshop, AssetWorkshopError
from core.asset_workshop_agent import AssetWorkshopAgent
from core.asset_workshop_registry import (
    WORKSHOP_DIR, active_asset_workshops, find_resumable, load_asset_workshop,
)
from core.asset_lifecycle import AssetLifecycleError, find_yaml_asset
from core.session_manager import active_sessions
from utils.asset_catalog import resolve_asset_path


router = APIRouter()


class StartPayload(BaseModel):
    asset_type: str
    asset_name: str
    session_id: str = ""


class ChatPayload(BaseModel):
    message: str
    mode: str = "refine"
    commit_changes: bool = False


class OperationsPayload(BaseModel):
    operations: list[dict[str, Any]] = Field(default_factory=list)


def _payload(workshop: AssetWorkshop) -> dict[str, Any]:
    return {
        "workshop_id": workshop.id, "asset_type": workshop.asset_type,
        "asset_name": workshop.draft.get("name", ""), "draft": workshop.draft,
        "proposed": workshop.proposed, "messages": workshop.messages,
        "suggested_actions": workshop.suggested_actions, "dirty": workshop.dirty,
        "published": workshop.published, "updated_at": workshop.updated_at,
    }


def _get(workshop_id: str) -> AssetWorkshop:
    workshop = load_asset_workshop(workshop_id)
    if not workshop:
        raise HTTPException(status_code=404, detail="资产工坊会话不存在")
    return workshop


def _target(payload: StartPayload) -> Path:
    if payload.asset_type not in {"characters", "styles", "entities"}:
        raise HTTPException(status_code=400, detail="该资产类型尚未接入工坊")
    if payload.session_id:
        game = active_sessions.get(payload.session_id)
        if not game:
            raise HTTPException(status_code=404, detail="会话失效")
        try:
            target = find_yaml_asset(Path(game.save_dir_path) / payload.asset_type, payload.asset_name)
        except AssetLifecycleError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not target:
            raise HTTPException(status_code=404, detail="本局资产不存在")
        return Path(target)
    target = resolve_asset_path(payload.asset_type, payload.asset_name)
    if not target:
        raise HTTPException(status_code=404, detail="全局资产不存在")
    return Path(target)


def _engine():
    from api.v1.game_routes import global_ai_engine
    return global_ai_engine


@router.post("/start")
def start_workshop(payload: StartPayload):
    target = _target(payload)
    source = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    resumed = find_resumable(payload.asset_type, target, source)
    if resumed:
        return {**_payload(resumed), "resumed": True}
    workshop = AssetWorkshop(str(uuid4()), payload.asset_type, target, source)
    active_asset_workshops[workshop.id] = workshop
    workshop.save_session(WORKSHOP_DIR)
    return {**_payload(workshop), "resumed": False}


@router.get("/{workshop_id}")
def get_workshop(workshop_id: str):
    return _payload(_get(workshop_id))


@router.post("/{workshop_id}/chat")
def chat_workshop(workshop_id: str, payload: ChatPayload):
    workshop = _get(workshop_id)
    engine = _engine()
    if not engine:
        raise HTTPException(status_code=500, detail="尚未配置可用的大语言模型")
    try:
        result = AssetWorkshopAgent(engine).respond(
            workshop, payload.message.strip(), payload.mode,
            commit_changes=payload.commit_changes,
        )
        workshop.save_session(WORKSHOP_DIR)
        return {**_payload(workshop), **result}
    except AssetWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{workshop_id}/operations")
def apply_operations(workshop_id: str, payload: OperationsPayload):
    workshop = _get(workshop_id)
    try:
        result = workshop.apply_operations(payload.operations, actor="player")
        workshop.clear_proposal()
        workshop.save_session(WORKSHOP_DIR)
        return {**_payload(workshop), "applied": result["applied"]}
    except AssetWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{workshop_id}/undo")
def undo_workshop(workshop_id: str):
    workshop = _get(workshop_id)
    try:
        workshop.undo()
        workshop.save_session(WORKSHOP_DIR)
        return _payload(workshop)
    except AssetWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{workshop_id}/publish")
def publish_workshop(workshop_id: str):
    workshop = _get(workshop_id)
    try:
        path = workshop.publish()
        workshop.save_session(WORKSHOP_DIR)
        return {**_payload(workshop), "published_path": str(path)}
    except (AssetWorkshopError, OSError, yaml.YAMLError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
