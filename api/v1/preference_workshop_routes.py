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
    list_preference_workshop_history,
    load_preference_workshop,
)
from core.session_manager import active_sessions
from core.user_preferences import UserPreferenceRepository
from api.v1.route_guards import guarded_workshop
from api.v1.streaming import workshop_chat_transaction, workshop_stream_response
from api.v1.generation_routes import GenerationPayload, controlled_generation
from api.v1.workshop_review_models import ReviewPayload, CreativeBriefPayload


router = APIRouter()
repository = UserPreferenceRepository()


class StartPayload(BaseModel):
    session_id: str = ""


class ChatPayload(GenerationPayload):
    message: str
    mode: str = "discover"
    commit_changes: bool = False


class OperationsPayload(BaseModel):
    operations: list[dict[str, Any]] = Field(default_factory=list)
    confirm_high_risk: bool = False


def _payload(workshop: PreferenceWorkshop):
    return {
        "workshop_id": workshop.id, "draft": workshop.draft,
        "creative_brief": workshop.creative_brief,
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
    from core.model_connections.runtime import get_task_engine
    return get_task_engine("workshop")


@router.post("/start")
def start_workshop(payload: StartPayload):
    profile = repository.load()
    history = list_preference_workshop_history()
    resumed, rebased = find_resumable(profile)
    if resumed:
        active_preference_workshops[resumed.id] = resumed
        return {**_payload(resumed), "resumed": True, "rebased": rebased, "history": history}
    game = active_sessions.get(payload.session_id) if payload.session_id else None
    include_sensitive = bool(game and game.story_settings.get("analyzeSensitivePreferences", False))
    workshop = PreferenceWorkshop(str(uuid4()), profile, include_sensitive=include_sensitive)
    active_preference_workshops[workshop.id] = workshop
    workshop.save_session(WORKSHOP_DIR)
    return {**_payload(workshop), "resumed": False, "rebased": False, "history": history}


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


@controlled_generation('workshop')
def _chat_workshop(workshop_id, payload, *, on_text_delta=None):
    workshop = _get(workshop_id)
    if workshop.published:
        raise HTTPException(status_code=409, detail="这轮工坊已经发布，请开启新一轮后再修改")
    engine = _engine()
    if not engine:
        raise HTTPException(status_code=500, detail="未找到可用的偏好分析模型")
    evidence = repository.load().get("evidence", [])
    try:
        result = workshop_chat_transaction(workshop, WORKSHOP_DIR, lambda candidate:
            PreferenceWorkshopAgent(engine).respond(candidate, payload.message.strip(), payload.mode, evidence,
                commit_changes=payload.commit_changes,
                **({"on_text_delta": on_text_delta} if on_text_delta is not None else {})))
        return {**_payload(workshop), **result}
    except (PreferenceWorkshopError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{workshop_id}/operations")
@guarded_workshop
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
@guarded_workshop
def approve_operation(workshop_id: str, operation_id: str):
    workshop = _get(workshop_id)
    try:
        workshop.approve(operation_id)
        workshop.save_session(WORKSHOP_DIR)
        return _payload(workshop)
    except PreferenceWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{workshop_id}/pending/{operation_id}")
@guarded_workshop
def reject_operation(workshop_id: str, operation_id: str):
    workshop = _get(workshop_id)
    try:
        workshop.reject(operation_id)
        workshop.save_session(WORKSHOP_DIR)
        return _payload(workshop)
    except PreferenceWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/{workshop_id}/creative-brief")
@guarded_workshop
def save_creative_brief(workshop_id: str, payload: CreativeBriefPayload):
    workshop = _get(workshop_id)
    try:
        workshop_chat_transaction(workshop, WORKSHOP_DIR, lambda candidate:
            candidate.set_creative_brief(payload.creative_brief))
        return _payload(workshop)
    except PreferenceWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{workshop_id}/review")
@guarded_workshop
def review_workshop(workshop_id: str, payload: ReviewPayload):
    workshop = _get(workshop_id)
    try:
        workshop_chat_transaction(workshop, WORKSHOP_DIR, lambda candidate:
            candidate.review_operations(payload.source, payload.operation_ids, payload.accept))
        return _payload(workshop)
    except PreferenceWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{workshop_id}/undo")
@guarded_workshop
def undo_workshop(workshop_id: str):
    workshop = _get(workshop_id)
    try:
        workshop.undo()
        workshop.save_session(WORKSHOP_DIR)
        return _payload(workshop)
    except PreferenceWorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{workshop_id}/publish")
@guarded_workshop
def publish_workshop(workshop_id: str):
    workshop = _get(workshop_id)
    try:
        workshop.publish(repository)
        workshop.save_session(WORKSHOP_DIR)
        return _payload(workshop)
    except PreferenceWorkshopError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
