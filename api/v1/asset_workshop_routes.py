"""Character, style, and undercurrent entity workshop API."""

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import yaml

from core.asset_workshop import AssetWorkshop, AssetWorkshopError
from core.asset_workshop_agent import AssetWorkshopAgent
from core.character_asset_write import CharacterWriteError
from core.asset_workshop_registry import (
    WORKSHOP_DIR, active_asset_workshops, find_resumable, load_asset_workshop,
    list_asset_workshop_history,
)
from core.asset_lifecycle import AssetLifecycleError, find_yaml_asset
from core.session_manager import active_sessions
from utils.asset_catalog import resolve_asset_path
from api.v1.route_guards import guarded_workshop
from api.v1.streaming import workshop_chat_transaction, workshop_stream_response
from api.v1.workshop_review_models import ReviewPayload, CreativeBriefPayload


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
        "creative_brief": workshop.creative_brief,
        "asset_name": workshop.draft.get("name", ""), "draft": workshop.draft,
        "proposed": workshop.proposed, "messages": workshop.messages,
        "suggested_actions": workshop.suggested_actions, "dirty": workshop.dirty,
        "published": workshop.published, "updated_at": workshop.updated_at,
    }


def _get(workshop_id: str) -> AssetWorkshop:
    try:
        workshop = load_asset_workshop(workshop_id)
    except (AssetWorkshopError, CharacterWriteError, OSError, ValueError):
        raise HTTPException(status_code=409, detail='工坊发布结果待核对或与当前资产冲突，草稿保留；未重新写入资产') from None
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
    from core.model_connections.runtime import get_task_engine
    return get_task_engine("workshop")


@router.post("/start")
def start_workshop(payload: StartPayload):
    target = _target(payload)
    source = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    resumed = find_resumable(payload.asset_type, target, source)
    history = list_asset_workshop_history(payload.asset_type, target)
    if resumed:
        return {**_payload(resumed), "resumed": True, "history": history}
    workshop = AssetWorkshop(str(uuid4()), payload.asset_type, target, source)
    if history:
        previous = load_asset_workshop(history[0]['workshop_id'])
        if previous:
            workshop.creative_brief = previous.creative_brief
            workshop.brief_edited = previous.brief_edited
    active_asset_workshops[workshop.id] = workshop
    workshop.save_session(WORKSHOP_DIR)
    return {**_payload(workshop), "resumed": False, "history": history}


@router.get("/{workshop_id}")
def get_workshop(workshop_id: str):
    return _payload(_get(workshop_id))


@router.post("/{workshop_id}/chat")
@guarded_workshop
def chat_workshop(workshop_id: str, payload: ChatPayload):
    return _chat_workshop(workshop_id, payload)


@router.post("/{workshop_id}/chat/stream")
def chat_workshop_stream(workshop_id: str, payload: ChatPayload):
    return workshop_stream_response(workshop_id, lambda emit: _chat_workshop(workshop_id, payload, on_text_delta=emit))


def _chat_workshop(workshop_id, payload, *, on_text_delta=None):
    workshop = _get(workshop_id)
    if workshop.published:
        raise HTTPException(status_code=409, detail="这轮工坊已经发布，请开启新一轮后再修改")
    engine = _engine()
    if not engine:
        raise HTTPException(status_code=500, detail="尚未配置可用的大语言模型")
    try:
        result = workshop_chat_transaction(workshop, WORKSHOP_DIR, lambda candidate:
            AssetWorkshopAgent(engine).respond(candidate, payload.message.strip(), payload.mode,
                commit_changes=payload.commit_changes,
                **({"on_text_delta": on_text_delta} if on_text_delta is not None else {})))
        return {**_payload(workshop), **result}
    except AssetWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{workshop_id}/operations")
@guarded_workshop
def apply_operations(workshop_id: str, payload: OperationsPayload):
    workshop = _get(workshop_id)
    try:
        def apply(candidate):
            result = candidate.apply_operations(payload.operations, actor='player')
            candidate.clear_proposal()
            return result
        result = workshop_chat_transaction(workshop, WORKSHOP_DIR, apply)
        return {**_payload(workshop), "applied": result["applied"]}
    except AssetWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{workshop_id}/creative-brief")
@guarded_workshop
def save_creative_brief(workshop_id: str, payload: CreativeBriefPayload):
    workshop = _get(workshop_id)
    try:
        workshop_chat_transaction(workshop, WORKSHOP_DIR, lambda candidate:
            candidate.set_creative_brief(payload.creative_brief))
        return _payload(workshop)
    except AssetWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{workshop_id}/review")
@guarded_workshop
def review_workshop(workshop_id: str, payload: ReviewPayload):
    workshop = _get(workshop_id)
    try:
        workshop_chat_transaction(workshop, WORKSHOP_DIR, lambda candidate:
            candidate.review_operations(payload.source, payload.operation_ids, payload.accept))
        return _payload(workshop)
    except AssetWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{workshop_id}/undo")
@guarded_workshop
def undo_workshop(workshop_id: str):
    workshop = _get(workshop_id)
    try:
        workshop_chat_transaction(workshop, WORKSHOP_DIR, lambda candidate: candidate.undo())
        return _payload(workshop)
    except AssetWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{workshop_id}/publish")
@guarded_workshop
def publish_workshop(workshop_id: str):
    workshop = _get(workshop_id)
    try:
        path = workshop.publish(WORKSHOP_DIR)
        if workshop.asset_type != 'characters':
            workshop.save_session(WORKSHOP_DIR)
        return {**_payload(workshop), "published_path": str(path)}
    except (AssetWorkshopError, CharacterWriteError, OSError, yaml.YAMLError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
