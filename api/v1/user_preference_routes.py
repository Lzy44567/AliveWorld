"""Global user preference profile API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any

from core.user_preferences import UserPreferenceRepository


router = APIRouter()
repository = UserPreferenceRepository()


class PreferenceUpdatePayload(BaseModel):
    updates: dict[str, Any] = Field(default_factory=dict)


@router.get("")
def get_preferences():
    return repository.load()


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

