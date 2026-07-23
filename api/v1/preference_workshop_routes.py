"""User preference workshop API."""

from uuid import uuid4
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.preference_workshop import PreferenceWorkshop, PreferenceWorkshopError
from core.preference_workshop_agent import PreferenceWorkshopAgent
from core.preference_workshop_registry import (
    WORKSHOP_DIR,
    active_preference_workshops,
    find_resumable,
    load_preference_workshop,
)
from core.session_manager import active_sessions
from core.user_preferences import UserPreferenceRepository


router = APIRouter()
repository = UserPreferenceRepository()


class StartPayload(BaseModel):
    session_id: str = ""


class ChatPayload(BaseModel):
    message: str
    mode: str = "discover"
    commit_changes: bool = False


class OperationsPayload(BaseModel):
    operations: list[dict[str, Any]] = Field(default_factory=list)
    confirm_high_risk: bool = False


def _payload(workshop: PreferenceWorkshop):
    return {
        "workshop_id": workshop.id, "draft": workshop.draft,
        "pending": workshop.pending, "proposed": workshop.proposed,
        "messages": workshop.messages, "suggested_actions": workshop.suggested_actions,
        "dirty": workshop.dirty, "published": workshop.published,
        "updated_at": workshop.updated_at, "include_sensitive": workshop.include_sensitive,
    }


def _get(workshop_id: str) -> PreferenceWorkshop:
    workshop = load_preference_workshop(workshop_id)
    if not workshop:
        raise HTTPException(status_code=404, detail="偏好工坊会话不存在")
    return workshop


def _engine():
    from api.v1.game_routes import global_preference_ai_engine, global_ai_engine
    return global_preference_ai_engine or global_ai_engine


@router.post("/start")
def start_workshop(payload: StartPayload):
    profile = repository.load()
    resumed, rebased = find_resumable(profile)
    if resumed:
        active_preference_workshops[resumed.id] = resumed
        return {**_payload(resumed), "resumed": True, "rebased": rebased}
    game = active_sessions.get(payload.session_id) if payload.session_id else None
    include_sensitive = bool(game and game.story_settings.get("analyzeSensitivePreferences", False))
    workshop = PreferenceWorkshop(str(uuid4()), profile, include_sensitive=include_sensitive)
    active_preference_workshops[workshop.id] = workshop
    workshop.save_session(WORKSHOP_DIR)
    return {**_payload(workshop), "resumed": False, "rebased": False}


@router.get("/{workshop_id}")
def get_workshop(workshop_id: str):
    return _payload(_get(workshop_id))


@router.post("/{workshop_id}/chat")
def chat_workshop(workshop_id: str, payload: ChatPayload):
    workshop = _get(workshop_id)
    engine = _engine()
    if not engine:
        raise HTTPException(status_code=500, detail="未找到可用的偏好分析模型")
    evidence = repository.load().get("evidence", [])
    try:
        result = PreferenceWorkshopAgent(engine).respond(
            workshop, payload.message.strip(), payload.mode, evidence,
            commit_changes=payload.commit_changes,
        )
        workshop.save_session(WORKSHOP_DIR)
        return {**_payload(workshop), **result}
    except (PreferenceWorkshopError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{workshop_id}/operations")
def apply_operations(workshop_id: str, payload: OperationsPayload):
    workshop = _get(workshop_id)
    try:
        result = workshop.apply_operations(
            payload.operations, confirm_high_risk=payload.confirm_high_risk
        )
        if not payload.confirm_high_risk:
            workshop.clear_proposal()
        workshop.save_session(WORKSHOP_DIR)
        return {**_payload(workshop), "applied": result["applied"]}
    except PreferenceWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{workshop_id}/pending/{operation_id}/approve")
def approve_operation(workshop_id: str, operation_id: str):
    workshop = _get(workshop_id)
    try:
        workshop.approve(operation_id)
        workshop.save_session(WORKSHOP_DIR)
        return _payload(workshop)
    except PreferenceWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{workshop_id}/pending/{operation_id}")
def reject_operation(workshop_id: str, operation_id: str):
    workshop = _get(workshop_id)
    try:
        workshop.reject(operation_id)
        workshop.save_session(WORKSHOP_DIR)
        return _payload(workshop)
    except PreferenceWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{workshop_id}/undo")
def undo_workshop(workshop_id: str):
    workshop = _get(workshop_id)
    try:
        workshop.undo()
        workshop.save_session(WORKSHOP_DIR)
        return _payload(workshop)
    except PreferenceWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{workshop_id}/publish")
def publish_workshop(workshop_id: str):
    workshop = _get(workshop_id)
    try:
        workshop.publish(repository)
        workshop.save_session(WORKSHOP_DIR)
        return _payload(workshop)
    except PreferenceWorkshopError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
