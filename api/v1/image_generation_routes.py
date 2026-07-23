from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core.image_generation import ImageGenerationService
from core.image_generation.service import ImageTaskError
from core.image_generation.providers.comfyui import ComfyUIProvider
from core.image_generation.runtime import get_image_runtime
from core.image_generation.references import ReferenceImageError, ReferenceImageRepository
from core.image_generation.prompt_compiler import ImagePromptCompiler, PromptCompilationError
from core.image_generation.portrait import PortraitAssignmentError, assign_current_portrait, assign_global_portrait, global_portrait_path, task_is_local_portrait
from core.image_generation.workflows import WorkflowError, WorkflowRepository
from core.image_generation.library import ImageLibraryScope, list_global_portrait_assets, list_library_scopes, resolve_library_scope
from core.session_manager import active_sessions
from utils.asset_catalog import resolve_asset_path


router = APIRouter()


class ImageTaskPayload(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)


class ComfyUIConfigPayload(BaseModel):
    base_url: str = "http://127.0.0.1:8188"


class WorkflowPayload(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)


class ReferenceImagePayload(BaseModel):
    filename: str
    role: str = "character"
    data_url: str


class PromptCompilePayload(BaseModel):
    intent: str = "scene_cg"
    user_request: str = ""
    source_message_id: str = ""
    character_ids: list[str] = Field(default_factory=list)
    character_context: str = ""
    style_preference: str = ""
    presentation_level: str = ""
    model_name: str = ""
    model_profile: str = ""


class CompileAndCreatePayload(BaseModel):
    task: Dict[str, Any] = Field(default_factory=dict)
    compile: PromptCompilePayload = Field(default_factory=PromptCompilePayload)


class PortraitAssignmentPayload(BaseModel):
    character_name: str
    image_index: int = 0
    scope: str = "local"


def _service(session_id: str) -> ImageGenerationService:
    game = active_sessions.get(session_id)
    if not game:
        raise HTTPException(status_code=404, detail="会话失效")
    return get_image_runtime(game.save_dir_path).service


def _runtime(session_id: str):
    game = active_sessions.get(session_id)
    if not game:
        raise HTTPException(status_code=404, detail="会话失效")
    return get_image_runtime(game.save_dir_path)


def _handle(call):
    try:
        return call()
    except ImageTaskError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _task_payload(session_id: str, task):
    data = task.to_dict()
    data["output_images"] = [
        f"/api/v1/game/{session_id}/images/tasks/{task.id}/files/{index}"
        for index, _path in enumerate(task.output_images)
    ]
    return data


def _library_task_payload(scope: ImageLibraryScope, task):
    data = task.to_dict()
    data["scope_id"] = scope.id
    data["scope_name"] = scope.name
    data["scope_kind"] = scope.kind
    data["output_images"] = [
        f"/api/v1/game/images/library/{scope.id}/tasks/{task.id}/files/{index}"
        for index, _path in enumerate(task.output_images)
    ]
    return data


@router.get("/images/library")
def list_image_library():
    items = []
    for scope in list_library_scopes():
        runtime = get_image_runtime(scope.root)
        items.extend(_library_task_payload(scope, task) for task in runtime.service.list())
    for asset in list_global_portrait_assets():
        items.append({
            "id": asset["id"],
            "scope_id": "global",
            "scope_name": "全局角色资产",
            "scope_kind": "global",
            "intent": "character_portrait",
            "status": "succeeded",
            "character_ids": [asset["character_name"]],
            "context_snapshot": {"asset_portrait": True, "referenced": asset["referenced"]},
            "output_images": [f"/api/v1/game/images/global-portraits/{asset['filename']}"],
            "created_at": "",
        })
    return sorted(items, key=lambda item: item.get("created_at", ""), reverse=True)


@router.get("/images/library/{scope_id}/tasks/{task_id}")
def get_library_image_task(scope_id: str, task_id: str):
    try:
        scope = resolve_library_scope(scope_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    runtime = get_image_runtime(scope.root)
    return _library_task_payload(scope, _handle(lambda: runtime.service.get(task_id)))


@router.delete("/images/library/{scope_id}/tasks/{task_id}")
def delete_library_image_task(scope_id: str, task_id: str):
    try:
        scope = resolve_library_scope(scope_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if scope.kind == "save" and task_is_local_portrait(scope.root, task_id):
        raise HTTPException(status_code=409, detail="该图片正在作为角色立绘使用，请先更换立绘")
    _handle(lambda: get_image_runtime(scope.root).service.delete(task_id))
    return {"status": "success"}


@router.post("/images/library/{scope_id}/tasks/{task_id}/regenerate")
def regenerate_library_image_task(scope_id: str, task_id: str):
    try:
        scope = resolve_library_scope(scope_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    runtime = get_image_runtime(scope.root)
    source = _handle(lambda: runtime.service.get(task_id))
    if not source.prompt.positive:
        raise HTTPException(status_code=400, detail="该任务需要故事上下文重新整理提示词，请先载入对应存档")
    task = _handle(lambda: runtime.service.regenerate(task_id))
    runtime.runner.start(task.id)
    return _library_task_payload(scope, task)


@router.get("/images/library/{scope_id}/tasks/{task_id}/files/{image_index}")
def get_library_generated_image(scope_id: str, task_id: str, image_index: int):
    try:
        scope = resolve_library_scope(scope_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    runtime = get_image_runtime(scope.root)
    task = _handle(lambda: runtime.service.get(task_id))
    if image_index < 0 or image_index >= len(task.output_images):
        raise HTTPException(status_code=404, detail="图片不存在")
    path = runtime.service.repository.outputs_dir / Path(task.output_images[image_index]).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片文件不存在")
    return FileResponse(path)


@router.post("/images/library/test")
def generate_global_comfyui_test_image(payload: ComfyUIConfigPayload, checkpoint: str, workflow_id: str = "builtin_basic"):
    scope = resolve_library_scope("global")
    runtime = get_image_runtime(scope.root)
    task = runtime.service.create("global", {
        "intent": "scene_cg",
        "provider_id": "comfyui",
        "workflow_id": workflow_id,
        "prompt": {
            "positive": "a cute fluffy white cat wearing a small blue ribbon, sitting on a sunny windowsill beside colorful flowers, warm soft light, detailed anime illustration, centered composition",
            "negative": "text, watermark, flag, national symbol, extra limbs, malformed animal, blurry, low quality",
            "width": 512,
            "height": 512,
        },
        "context_snapshot": {"test_task": True, "library_scope": "global"},
        "provider_options": {"base_url": payload.base_url, "checkpoint": checkpoint},
    })
    runtime.runner.start(task.id)
    return _library_task_payload(scope, task)


@router.get("/{session_id}/images/tasks")
def list_image_tasks(session_id: str):
    return [_task_payload(session_id, task) for task in _handle(lambda: _service(session_id).list())]


@router.post("/{session_id}/images/tasks")
def create_image_task(session_id: str, payload: ImageTaskPayload):
    game = active_sessions.get(session_id)
    if not game:
        raise HTTPException(status_code=404, detail="会话失效")
    runtime = _runtime(session_id)
    task = _handle(lambda: runtime.service.create(game.save_name or session_id, payload.data))
    runtime.runner.start(task.id)
    game.record_preference_interaction(
        "generation",
        "玩家主动为当前故事生成了一张图片。",
        "仅记录生成行为；未把正文、图片提示词或潜在敏感内容写入偏好证据。",
    )
    return _task_payload(session_id, task)


def _compile_payload(game, payload: PromptCompilePayload) -> dict[str, Any]:
    story_text = ""
    if payload.source_message_id:
        message = next((item for item in game.history.get("chat_messages", []) if item.get("id") == payload.source_message_id), None)
        if not message or message.get("role") != "ai":
            raise PromptCompilationError("找不到对应的 AI 正文")
        story_text = str(message.get("content", ""))
    active_world, _ = game.build_visible_world_info(payload.user_request or story_text)
    return {
        "intent": payload.intent,
        "user_request": payload.user_request,
        "story_text": story_text,
        "character_context": payload.character_context,
        "world_context": active_world,
        "style_preference": payload.style_preference,
        "narrative_style_context": str(getattr(game.ctx_mgr, "style_info", ""))[:3000],
        "presentation_level": payload.presentation_level,
        "model_name": payload.model_name,
        "model_profile": payload.model_profile,
    }


def _global_portrait_task_data(task_data: dict[str, Any], character_name: str) -> dict[str, Any]:
    data = dict(task_data)
    data["intent"] = "character_portrait"
    data["character_ids"] = [character_name]
    data["context_snapshot"] = {
        **dict(data.get("context_snapshot") or {}),
        "character_name": character_name,
        "portrait_scope": "global",
        "auto_assign_portrait": True,
        "library_scope": "global",
    }
    return data


@router.post("/images/library/global/character-portraits")
def create_global_character_portrait(payload: ImageTaskPayload):
    character_name = str((payload.data.get("context_snapshot") or {}).get("character_name", "")).strip()
    if not character_name:
        raise HTTPException(status_code=400, detail="缺少全局角色名称")
    if not resolve_asset_path("characters", character_name):
        raise HTTPException(status_code=404, detail="全局角色卡不存在")
    scope = resolve_library_scope("global")
    runtime = get_image_runtime(scope.root)
    task = _handle(lambda: runtime.service.create("global", _global_portrait_task_data(payload.data, character_name)))
    runtime.runner.start(task.id)
    return _library_task_payload(scope, task)


@router.post("/images/library/global/character-portraits/compile-and-start")
def compile_and_create_global_character_portrait(payload: CompileAndCreatePayload):
    from api.v1.game_routes import global_ai_engine

    if not global_ai_engine:
        raise HTTPException(status_code=500, detail="未找到 config.yml")
    character_name = str((payload.task.get("context_snapshot") or {}).get("character_name", "")).strip()
    if not character_name:
        raise HTTPException(status_code=400, detail="缺少全局角色名称")
    if not resolve_asset_path("characters", character_name):
        raise HTTPException(status_code=404, detail="全局角色卡不存在")
    scope = resolve_library_scope("global")
    runtime = get_image_runtime(scope.root)
    task_data = _global_portrait_task_data(payload.task, character_name)
    task_data["prompt"] = {**dict(task_data.get("prompt") or {}), "positive": ""}
    task_data["context_snapshot"] = {
        **dict(task_data.get("context_snapshot") or {}),
        "prompt_compile_request": payload.compile.model_dump(),
    }
    task = _handle(lambda: runtime.service.create("global", task_data))
    compile_data = {
        "intent": "character_portrait",
        "user_request": payload.compile.user_request,
        "story_text": "",
        "character_context": payload.compile.character_context,
        "world_context": "",
        "style_preference": payload.compile.style_preference,
        "narrative_style_context": "",
        "presentation_level": payload.compile.presentation_level,
        "model_name": payload.compile.model_name,
        "model_profile": payload.compile.model_profile,
    }
    runtime.pipeline.compile_and_start(task.id, lambda: ImagePromptCompiler(global_ai_engine).compile(compile_data))
    return _library_task_payload(scope, runtime.service.get(task.id))


@router.post("/{session_id}/images/tasks/compile-and-start")
def compile_and_create_image_task(session_id: str, payload: CompileAndCreatePayload):
    game = active_sessions.get(session_id)
    if not game:
        raise HTTPException(status_code=404, detail="会话失效")
    runtime = _runtime(session_id)
    task_data = dict(payload.task)
    task_data["prompt"] = {**dict(task_data.get("prompt") or {}), "positive": ""}
    task_data["context_snapshot"] = {
        **dict(task_data.get("context_snapshot") or {}),
        "prompt_compile_request": payload.compile.model_dump(),
    }
    task = _handle(lambda: runtime.service.create(game.save_name or session_id, task_data))
    runtime.pipeline.compile_and_start(
        task.id,
        lambda: ImagePromptCompiler(game.ai_engine).compile(_compile_payload(game, payload.compile)),
    )
    game.record_preference_interaction(
        "generation",
        "玩家主动为当前故事生成了一张图片。",
        "仅记录生成行为；未把正文、图片提示词或潜在敏感内容写入偏好证据。",
    )
    return _task_payload(session_id, runtime.service.get(task.id))


@router.get("/{session_id}/images/tasks/{task_id}")
def get_image_task(session_id: str, task_id: str):
    return _task_payload(session_id, _handle(lambda: _service(session_id).get(task_id)))


@router.post("/{session_id}/images/tasks/{task_id}/cancel")
def cancel_image_task(session_id: str, task_id: str):
    return _task_payload(session_id, _handle(lambda: _runtime(session_id).runner.cancel(task_id)))


@router.post("/{session_id}/images/tasks/{task_id}/retry")
def retry_image_task(session_id: str, task_id: str):
    runtime = _runtime(session_id)
    task = _handle(lambda: runtime.service.retry(task_id))
    runtime.runner.start(task.id)
    return _task_payload(session_id, task)


@router.post("/{session_id}/images/tasks/{task_id}/regenerate")
def regenerate_image_task(session_id: str, task_id: str):
    runtime = _runtime(session_id)
    source = _handle(lambda: runtime.service.get(task_id))
    compile_request = source.context_snapshot.get("prompt_compile_request")
    if not source.prompt.positive and not isinstance(compile_request, dict):
        raise HTTPException(status_code=400, detail="原任务没有可重用的提示词或编译上下文")
    task = _handle(lambda: runtime.service.regenerate(task_id))
    if task.prompt.positive:
        runtime.runner.start(task.id)
    else:
        game = active_sessions.get(session_id)
        if not game:
            raise HTTPException(status_code=404, detail="会话失效")
        compile_payload = PromptCompilePayload(**compile_request)
        runtime.pipeline.compile_and_start(
            task.id,
            lambda: ImagePromptCompiler(game.ai_engine).compile(_compile_payload(game, compile_payload)),
        )
    game = active_sessions.get(session_id)
    if game:
        game.record_preference_interaction(
            "generation",
            "玩家要求重新生成一张故事图片；原因可能是画质、构图、角色一致性或内容不符合预期。",
            "仅记录重新生成行为；未上传原图片或生图提示词。",
        )
    return _task_payload(session_id, runtime.service.get(task.id))


@router.delete("/{session_id}/images/tasks/{task_id}")
def delete_image_task(session_id: str, task_id: str):
    game = active_sessions.get(session_id)
    if game and task_is_local_portrait(game.save_dir_path, task_id):
        raise HTTPException(status_code=409, detail="该图片正在作为本局角色立绘使用，请先更换立绘")
    _handle(lambda: _service(session_id).delete(task_id))
    return {"status": "success"}


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


@router.get("/{session_id}/images/references")
def list_reference_images(session_id: str):
    game = active_sessions.get(session_id)
    if not game:
        raise HTTPException(status_code=404, detail="会话失效")
    repository = ReferenceImageRepository(game.save_dir_path)
    return [{**item.to_dict(), "url": f"/api/v1/game/{session_id}/images/references/{item.id}/file"} for item in repository.list()]


@router.post("/{session_id}/images/references")
def upload_reference_image(session_id: str, payload: ReferenceImagePayload):
    game = active_sessions.get(session_id)
    if not game:
        raise HTTPException(status_code=404, detail="会话失效")
    try:
        item = ReferenceImageRepository(game.save_dir_path).add_data_url(payload.filename, payload.role, payload.data_url)
    except ReferenceImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**item.to_dict(), "url": f"/api/v1/game/{session_id}/images/references/{item.id}/file"}


@router.get("/{session_id}/images/references/{reference_id}/file")
def get_reference_image(session_id: str, reference_id: str):
    game = active_sessions.get(session_id)
    if not game:
        raise HTTPException(status_code=404, detail="会话失效")
    try:
        path = ReferenceImageRepository(game.save_dir_path).file_path(reference_id)
    except ReferenceImageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path)


@router.delete("/{session_id}/images/references/{reference_id}")
def delete_reference_image(session_id: str, reference_id: str):
    game = active_sessions.get(session_id)
    if not game:
        raise HTTPException(status_code=404, detail="会话失效")
    runtime = _runtime(session_id)
    if any(reference.id == reference_id for task in runtime.service.list() for reference in task.prompt.references):
        raise HTTPException(status_code=409, detail="参考图已被生图任务引用，不能删除")
    try:
        ReferenceImageRepository(game.save_dir_path).remove(reference_id)
    except ReferenceImageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "success"}


@router.post("/{session_id}/images/providers/comfyui/test")
def generate_comfyui_test_image(session_id: str, payload: ComfyUIConfigPayload, checkpoint: str, workflow_id: str = "builtin_basic"):
    runtime = _runtime(session_id)
    game = active_sessions[session_id]
    task = runtime.service.create(game.save_name or session_id, {
        "intent": "scene_cg",
        "provider_id": "comfyui",
        "workflow_id": workflow_id,
        "prompt": {
            "positive": "a cute fluffy white cat wearing a small blue ribbon, sitting on a sunny windowsill beside colorful flowers, warm soft light, detailed anime illustration, centered composition",
            "negative": "text, watermark, flag, national symbol, extra limbs, malformed animal, blurry, low quality",
            "width": 512,
            "height": 512,
        },
        "context_snapshot": {"test_task": True},
        "provider_options": {"base_url": payload.base_url, "checkpoint": checkpoint},
    })
    runtime.runner.start(task.id)
    return _task_payload(session_id, task)


@router.post("/{session_id}/images/prompts/compile")
def compile_image_prompt(session_id: str, payload: PromptCompilePayload):
    game = active_sessions.get(session_id)
    if not game:
        raise HTTPException(status_code=404, detail="会话失效")
    try:
        return ImagePromptCompiler(game.ai_engine).compile(_compile_payload(game, payload))
    except PromptCompilationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{session_id}/images/tasks/{task_id}/set-portrait")
def set_character_portrait(session_id: str, task_id: str, payload: PortraitAssignmentPayload):
    game = active_sessions.get(session_id)
    if not game:
        raise HTTPException(status_code=404, detail="会话失效")
    task = _handle(lambda: _service(session_id).get(task_id))
    try:
        if payload.scope == "global":
            runtime = _runtime(session_id)
            character = assign_global_portrait(payload.character_name, task, runtime.service.repository.outputs_dir, payload.image_index)
        else:
            character = assign_current_portrait(game.save_dir_path, payload.character_name, task, payload.image_index)
    except PortraitAssignmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "success", "character": character}


@router.get("/images/global-portraits/{filename}")
def get_global_portrait(filename: str):
    try:
        return FileResponse(global_portrait_path(filename))
    except PortraitAssignmentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{session_id}/images/tasks/{task_id}/files/{image_index}")
def get_generated_image(session_id: str, task_id: str, image_index: int):
    task = _handle(lambda: _service(session_id).get(task_id))
    if image_index < 0 or image_index >= len(task.output_images):
        raise HTTPException(status_code=404, detail="图片不存在")
    runtime = _runtime(session_id)
    path = runtime.service.repository.outputs_dir / Path(task.output_images[image_index]).name
    try:
        path.resolve().relative_to(runtime.service.repository.outputs_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="图片路径无效") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片文件不存在")
    return FileResponse(path)
