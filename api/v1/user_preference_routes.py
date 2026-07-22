"""Global user preference profile API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any

from core.user_preferences import UserPreferenceRepository
from core.session_manager import active_sessions


router = APIRouter()
repository = UserPreferenceRepository()


class PreferenceUpdatePayload(BaseModel):
    updates: dict[str, Any] = Field(default_factory=dict)


class PreferenceDeclarationPayload(BaseModel):
    text: str
    session_id: str = ""
    category: str = "other"
    polarity: str = "prefer"
    sensitive: bool = False


class PreferenceAnalysisPayload(BaseModel):
    session_id: str
    force: bool = False


@router.get("")
def get_preferences():
    profile = repository.load()
    profile["pending_count"] = sum(1 for item in profile["preferences"] if item.get("status") == "candidate")
    profile["pending_evidence_count"] = sum(1 for item in profile["evidence"] if not item.get("analyzed"))
    return profile


@router.post("/declare")
def declare_preference(payload: PreferenceDeclarationPayload):
    game = active_sessions.get(payload.session_id) if payload.session_id else None
    item = repository.declare(
        payload.text, save_name=getattr(game, "save_name", ""), category=payload.category,
        polarity=payload.polarity, sensitive=payload.sensitive,
    )
    if item is None:
        raise HTTPException(status_code=400, detail="偏好内容不能为空")
    return {"preference": item}


@router.post("/analyze")
def analyze_preferences(payload: PreferenceAnalysisPayload):
    game = active_sessions.get(payload.session_id)
    if not game:
        raise HTTPException(status_code=404, detail="请先载入一个故事，以确定偏好分析模型")
    result = game.preference_analysis.analyze_now(
        repository,
        include_sensitive=game.story_settings.get("analyzeSensitivePreferences", False),
        force=payload.force,
    )
    if result.get("error"):
        raise HTTPException(status_code=502, detail=result["error"])
    return result


@router.post("/{preference_id}")
def update_preference(preference_id: str, payload: PreferenceUpdatePayload):
    item = repository.update(preference_id, payload.updates)
    if item is None:
        raise HTTPException(status_code=404, detail="偏好不存在")
    return {"preference": item}


@router.delete("/{preference_id}")
def delete_preference(preference_id: str):
    if not repository.delete(preference_id):
        raise HTTPException(status_code=404, detail="偏好不存在")
    return {"status": "success"}
