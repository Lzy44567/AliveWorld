"""Protected local developer tools: prompt slice inspection and overrides."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from core.developer_access import developer_access
from core.prompt_studio import PromptOverrideStore, list_slices, require_slice
from core.prompt_variables import list_variables


router = APIRouter()
prompt_store = PromptOverrideStore()


class PasswordPayload(BaseModel):
    password: str = Field(min_length=1, max_length=512)


class OverridePayload(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)


def _token(authorization: str = Header(default="")) -> str:
    prefix = "Bearer "
    return authorization[len(prefix):].strip() if authorization.startswith(prefix) else ""


def _require(token: str) -> None:
    try:
        developer_access.require(token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/status")
async def status():
    return {"configured": developer_access.configured}


@router.post("/setup")
async def setup(payload: PasswordPayload):
    try:
        token = developer_access.setup(payload.password)
        return {"token": token, "expiresIn": developer_access.TOKEN_TTL}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/unlock")
async def unlock(payload: PasswordPayload):
    try:
        token = developer_access.unlock(payload.password)
        return {"token": token, "expiresIn": developer_access.TOKEN_TTL}
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/lock")
async def lock(authorization: str = Header(default="")):
    token = _token(authorization)
    developer_access.lock(token)
    return {"status": "locked"}


@router.get("/prompts")
async def prompts(authorization: str = Header(default="")):
    _require(_token(authorization))
    return {"slices": list_slices(prompt_store), "variables": list_variables()}


@router.put("/prompts/{slice_id}")
async def save_prompt(slice_id: str, payload: OverridePayload, authorization: str = Header(default="")):
    _require(_token(authorization))
    try:
        require_slice(slice_id)
        record = prompt_store.save(slice_id, payload.content)
        return {"status": "success", "overrideVersion": record["version"]}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/prompts/{slice_id}")
async def restore_prompt(slice_id: str, authorization: str = Header(default="")):
    _require(_token(authorization))
    try:
        require_slice(slice_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "success", "restored": prompt_store.restore(slice_id)}
