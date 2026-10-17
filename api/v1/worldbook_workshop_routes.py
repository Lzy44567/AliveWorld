from pathlib import Path
import uuid

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from core.worldbook_workshop import WorkshopError, WorldbookWorkshop
from core.worldbook_workshop_agent import WorldbookWorkshopAgent
from core.worldbook_embeddings import embedding_manager
from core.worldbook import normalize_worldbook, worldbook_write_guard
from core.worldbook_revisions import reconcile_capture_history
from core.session_manager import active_sessions, mutation_guard, save_identity, MutationBusyError
from core.worldbook_workshop_registry import (
    WORKSHOP_DIR, active_workshops, list_worldbook_workshop_history,
    load_worldbook_workshop,
)
from utils.asset_catalog import resolve_asset_path
from utils.file_io import DATA_DIR, WORLD_DIR, SAVE_DIR
from api.v1.route_guards import guarded_workshop
from api.v1.streaming import workshop_chat_transaction, workshop_stream_response


router = APIRouter()


class StartWorkshopRequest(BaseModel):
    worldbook_name: str
    session_id: Optional[str] = None


class ApplyOperationsRequest(BaseModel):
    operations: List[Dict[str, Any]] = Field(default_factory=list)
    confirm_high_risk: bool = False


class PublishRequest(BaseModel):
    worldbook_name: Optional[str] = None


class ReviewOperationsRequest(BaseModel):
    source: str
    operation_ids: List[str] = Field(min_length=1)
    accept: bool


class CreativeBriefRequest(BaseModel):
    creative_brief: str = Field(max_length=2000)


class WorkshopChatRequest(BaseModel):
    message: str
    mode: str = "expand"
    commit_changes: bool = False


class EmbeddingToggleRequest(BaseModel):
    enabled: bool


@router.get("/workshops/embeddings/status")
def embedding_status():
    return embedding_manager.status()


@router.post("/workshops/embeddings/download")
def download_embedding_model():
    return embedding_manager.download_in_background()


@router.post("/workshops/embeddings/pause")
def pause_embedding_download():
    return embedding_manager.pause_download()


@router.delete("/workshops/embeddings/model")
def uninstall_embedding_model():
    return embedding_manager.uninstall()


@router.post("/workshops/embeddings/toggle")
def toggle_embeddings(payload: EmbeddingToggleRequest):
    return embedding_manager.set_enabled(payload.enabled)


def _get(workshop_id: str) -> WorldbookWorkshop:
    workshop = load_worldbook_workshop(workshop_id)
    if workshop:
        return workshop
    raise HTTPException(status_code=404, detail="世界书工坊会话不存在")


def _payload(workshop: WorldbookWorkshop):
    return {"workshop_id": workshop.id, "draft": workshop.draft, "pending": workshop.pending, "proposed": workshop.proposed, "messages": workshop.messages, "suggested_actions": workshop.suggested_actions, "creative_brief": workshop.creative_brief, "dirty": workshop.dirty, "published": workshop.published, "updated_at": workshop.updated_at}


def _find_resumable(target_path: Path, current_book: dict[str, Any]) -> tuple[WorldbookWorkshop | None, int]:
    candidates = []
    stale_count = 0
    if WORKSHOP_DIR.exists():
        import json
        for path in WORKSHOP_DIR.glob("*.json"):
            try:
                item = WorldbookWorkshop.from_dict(json.loads(path.read_text(encoding="utf-8")))
                has_unpublished_changes = item.dirty or normalize_worldbook(item.draft) != current_book
                if item.target_path.resolve() == target_path.resolve() and not item.published and has_unpublished_changes:
                    if item.is_based_on(current_book):
                        candidates.append(item)
                    else:
                        stale_count += 1
            except (OSError, ValueError, KeyError):
                continue
    return (max(candidates, key=lambda item: item.updated_at) if candidates else None, stale_count)


@router.post("/workshops/start")
def start_workshop(payload: StartWorkshopRequest):
    source_path = None
    if payload.session_id:
        from core.session_manager import active_sessions
        game = active_sessions.get(payload.session_id)
        if not game:
            raise HTTPException(status_code=404, detail="当前故事会话不存在，请重新载入存档")
        for candidate in (Path(game.save_dir_path) / "worldbooks").glob("*.yml"):
            try:
                if (yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}).get("name") == payload.worldbook_name:
                    source_path = candidate
                    break
            except (OSError, yaml.YAMLError):
                continue
    else:
        source_path = resolve_asset_path("worldbooks", payload.worldbook_name)
    if not source_path:
        raise HTTPException(status_code=404, detail="世界书不存在")
    source = yaml.safe_load(source_path.read_text(encoding="utf-8")) or {}
    if payload.session_id:
        source, _ = reconcile_capture_history(normalize_worldbook(source), game.history.get('story_turns', []))
    current_book = normalize_worldbook(source)
    resumed, stale_count = _find_resumable(source_path, current_book)
    history = list_worldbook_workshop_history(source_path)
    if resumed:
        if payload.session_id:
            resumed.local_save_path = str(game.save_dir_path)
        active_workshops[resumed.id] = resumed
        return {**_payload(resumed), "resumed": True, "stale_drafts_preserved": stale_count, "history": history}
    workshop = WorldbookWorkshop(str(uuid.uuid4()), source_path, source)
    if history:
        previous = load_worldbook_workshop(history[0]["workshop_id"])
        if previous:
            workshop.creative_brief = previous.creative_brief
            workshop.brief_edited = previous.brief_edited
    if payload.session_id:
        workshop.local_save_path = str(game.save_dir_path)
    active_workshops[workshop.id] = workshop
    workshop.save_session(WORKSHOP_DIR)
    return {**_payload(workshop), "resumed": False, "stale_drafts_preserved": stale_count, "history": history}


@router.get("/workshops/{workshop_id}")
def get_workshop(workshop_id: str):
    return _payload(_get(workshop_id))


@router.put("/workshops/{workshop_id}/creative-brief")
@guarded_workshop
def save_creative_brief(workshop_id: str, payload: CreativeBriefRequest):
    workshop = _get(workshop_id)
    try:
        workshop_chat_transaction(workshop, WORKSHOP_DIR, lambda candidate:
            candidate.set_creative_brief(payload.creative_brief))
        return _payload(workshop)
    except WorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/workshops/{workshop_id}/operations")
@guarded_workshop
def apply_operations(workshop_id: str, payload: ApplyOperationsRequest):
    workshop = _get(workshop_id)
    try:
        result = workshop.apply_operations(payload.operations, confirm_high_risk=payload.confirm_high_risk)
        if not payload.confirm_high_risk:
            workshop.clear_proposal()
        workshop.save_session(WORKSHOP_DIR)
        return {**_payload(workshop), "applied": result["applied"]}
    except WorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/workshops/{workshop_id}/chat")
@guarded_workshop
def chat_workshop(workshop_id: str, payload: WorkshopChatRequest):
    return _chat_workshop(workshop_id, payload)


@router.post("/workshops/{workshop_id}/chat/stream")
def chat_workshop_stream(workshop_id: str, payload: WorkshopChatRequest):
    return workshop_stream_response(workshop_id, lambda emit: _chat_workshop(workshop_id, payload, on_text_delta=emit))


def _chat_workshop(workshop_id, payload, *, on_text_delta=None):
    workshop = _get(workshop_id)
    if workshop.published:
        raise HTTPException(status_code=409, detail="这轮工坊已经发布，请开启新一轮后再修改")
    from core.model_connections.runtime import get_task_engine
    engine = get_task_engine("workshop")
    if not engine:
        raise HTTPException(status_code=500, detail="请先在设置中配置可用的大语言模型 API")
    try:
        result = workshop_chat_transaction(workshop, WORKSHOP_DIR, lambda candidate:
            WorldbookWorkshopAgent(engine).respond(candidate, payload.message.strip(), payload.mode,
                commit_changes=payload.commit_changes,
                **({"on_text_delta": on_text_delta} if on_text_delta is not None else {})))
        return {**_payload(workshop), **result}
    except (WorkshopError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/workshops/{workshop_id}/pending/{operation_id}/approve")
@guarded_workshop
def approve_operation(workshop_id: str, operation_id: str):
    workshop = _get(workshop_id)
    try:
        workshop.approve(operation_id)
        workshop.save_session(WORKSHOP_DIR)
        return _payload(workshop)
    except WorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/workshops/{workshop_id}/review")
@guarded_workshop
def review_operations(workshop_id: str, payload: ReviewOperationsRequest):
    workshop = _get(workshop_id)
    try:
        workshop_chat_transaction(workshop, WORKSHOP_DIR, lambda candidate:
            candidate.review_operations(payload.source, payload.operation_ids, accept=payload.accept))
        return _payload(workshop)
    except WorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/workshops/{workshop_id}/pending/{operation_id}")
@guarded_workshop
def reject_operation(workshop_id: str, operation_id: str):
    workshop = _get(workshop_id)
    try:
        workshop.reject(operation_id)
        workshop.save_session(WORKSHOP_DIR)
        return _payload(workshop)
    except WorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/workshops/{workshop_id}/undo")
@guarded_workshop
def undo_workshop(workshop_id: str):
    workshop = _get(workshop_id)
    try:
        workshop.undo()
        workshop.save_session(WORKSHOP_DIR)
        return _payload(workshop)
    except WorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/workshops/{workshop_id}/publish")
@guarded_workshop
def publish_workshop(workshop_id: str, payload: PublishRequest):
    workshop = _get(workshop_id)
    # Old persisted local drafts predate explicit ownership metadata.
    if not workshop.local_save_path and Path(SAVE_DIR).resolve() in workshop.target_path.resolve().parents:
        workshop.local_save_path = str(workshop.target_path.resolve().parent.parent)
    if workshop.published:
        raise HTTPException(status_code=409, detail="这轮工坊已经发布，请开启新一轮后再修改")
    target = workshop.target_path
    if payload.worldbook_name:
        safe_name = "".join(char for char in payload.worldbook_name if char.isalnum() or char in " _-").strip()
        if not safe_name:
            raise HTTPException(status_code=400, detail="世界书名称无效")
        workshop.draft["name"] = payload.worldbook_name.strip()
        target = Path(WORLD_DIR) / f"{safe_name}.yml"
    elif target.name.endswith(".template.yml") or workshop.draft.get("is_template") is True:
        raise HTTPException(status_code=400, detail="模板世界书必须另存为个人世界书")
    if workshop.local_save_path:
        game = next((g for g in active_sessions.values()
                     if g.save_dir_path and Path(g.save_dir_path).resolve() == Path(workshop.local_save_path).resolve()), None)
        if game is None:
            raise HTTPException(status_code=409, detail="请先载入该工坊所属的故事，再发布局内修改")
        try:
            with mutation_guard('story', save_identity(game.save_dir_path)), worldbook_write_guard(workshop.target_path):
                source = normalize_worldbook(yaml.safe_load(workshop.target_path.read_text(encoding='utf-8')))
                current, _ = reconcile_capture_history(source, game.history.get('story_turns', []))
                if not workshop.is_based_on(current):
                    raise HTTPException(status_code=409, detail="世界书或来源回合已变化，请重新打开工坊；当前草稿仍保留")
                workshop.publish(target)
        except MutationBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    else:
        workshop.publish(target)
    workshop.target_path = target
    workshop.save_session(WORKSHOP_DIR)
    return {**_payload(workshop), "published_path": str(target)}
