from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.image_generation import ImageGenerationService, ImageTaskRepository
from core.image_generation.service import ImageTaskError
from core.image_generation.providers.comfyui import ComfyUIProvider
from core.image_generation.workflows import WorkflowError, WorkflowRepository
from core.session_manager import active_sessions


router = APIRouter()


class ImageTaskPayload(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)


class ComfyUIConfigPayload(BaseModel):
    base_url: str = "http://127.0.0.1:8188"


class WorkflowPayload(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)


def _service(session_id: str) -> ImageGenerationService:
    game = active_sessions.get(session_id)
    if not game:
        raise HTTPException(status_code=404, detail="会话失效")
    return ImageGenerationService(ImageTaskRepository(game.save_dir_path))


def _handle(call):
    try:
        return call()
    except ImageTaskError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{session_id}/images/tasks")
def list_image_tasks(session_id: str):
    return [task.to_dict() for task in _handle(lambda: _service(session_id).list())]


@router.post("/{session_id}/images/tasks")
def create_image_task(session_id: str, payload: ImageTaskPayload):
    game = active_sessions.get(session_id)
    if not game:
        raise HTTPException(status_code=404, detail="会话失效")
    task = _handle(lambda: _service(session_id).create(game.save_name or session_id, payload.data))
    return task.to_dict()


@router.get("/{session_id}/images/tasks/{task_id}")
def get_image_task(session_id: str, task_id: str):
    return _handle(lambda: _service(session_id).get(task_id)).to_dict()


@router.post("/{session_id}/images/tasks/{task_id}/cancel")
def cancel_image_task(session_id: str, task_id: str):
    return _handle(lambda: _service(session_id).cancel(task_id)).to_dict()


@router.post("/{session_id}/images/tasks/{task_id}/retry")
def retry_image_task(session_id: str, task_id: str):
    return _handle(lambda: _service(session_id).retry(task_id)).to_dict()


@router.post("/images/providers/comfyui/check")
def check_comfyui(payload: ComfyUIConfigPayload):
    return ComfyUIProvider(payload.base_url).check().__dict__


@router.post("/images/providers/comfyui/checkpoints")
def list_comfyui_checkpoints(payload: ComfyUIConfigPayload):
    provider = ComfyUIProvider(payload.base_url)
    capabilities = provider.check()
    if not capabilities.connected:
        raise HTTPException(status_code=503, detail=capabilities.message)
    return {"checkpoints": capabilities.checkpoints}


@router.get("/images/workflows")
def list_image_workflows():
    return [item.summary() for item in WorkflowRepository().list()]


@router.post("/images/workflows")
def import_image_workflow(payload: WorkflowPayload):
    try:
        return WorkflowRepository().import_definition(payload.data).summary()
    except WorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
