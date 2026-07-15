from pathlib import Path
import uuid

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from core.worldbook_workshop import WorkshopError, WorldbookWorkshop
from core.worldbook_workshop_agent import WorldbookWorkshopAgent
from core.worldbook_embeddings import embedding_manager
from core.worldbook import normalize_worldbook
from utils.asset_catalog import resolve_asset_path
from utils.file_io import DATA_DIR, WORLD_DIR


router = APIRouter()
WORKSHOP_DIR = Path(DATA_DIR) / "workshops"
active_workshops: Dict[str, WorldbookWorkshop] = {}


class StartWorkshopRequest(BaseModel):
    worldbook_name: str
    session_id: Optional[str] = None


class ApplyOperationsRequest(BaseModel):
    operations: List[Dict[str, Any]] = Field(default_factory=list)
    confirm_high_risk: bool = False


class PublishRequest(BaseModel):
    worldbook_name: Optional[str] = None


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
    workshop = active_workshops.get(workshop_id)
    if workshop:
        return workshop
    path = WORKSHOP_DIR / f"{workshop_id}.json"
    if path.exists():
        import json
        workshop = WorldbookWorkshop.from_dict(json.loads(path.read_text(encoding="utf-8")))
        active_workshops[workshop_id] = workshop
        return workshop
    raise HTTPException(status_code=404, detail="世界书工坊会话不存在")


def _payload(workshop: WorldbookWorkshop):
    return {"workshop_id": workshop.id, "draft": workshop.draft, "pending": workshop.pending, "proposed": workshop.proposed, "messages": workshop.messages, "suggested_actions": workshop.suggested_actions, "dirty": workshop.dirty, "published": workshop.published, "updated_at": workshop.updated_at}


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
    current_book = normalize_worldbook(source)
    resumed, stale_count = _find_resumable(source_path, current_book)
    if resumed:
        active_workshops[resumed.id] = resumed
        return {**_payload(resumed), "resumed": True, "stale_drafts_preserved": stale_count}
    workshop = WorldbookWorkshop(str(uuid.uuid4()), source_path, source)
    active_workshops[workshop.id] = workshop
    workshop.save_session(WORKSHOP_DIR)
    return {**_payload(workshop), "resumed": False, "stale_drafts_preserved": stale_count}


@router.get("/workshops/{workshop_id}")
def get_workshop(workshop_id: str):
    return _payload(_get(workshop_id))


@router.post("/workshops/{workshop_id}/operations")
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
def chat_workshop(workshop_id: str, payload: WorkshopChatRequest):
    workshop = _get(workshop_id)
    from api.v1.game_routes import global_ai_engine
    if not global_ai_engine:
        raise HTTPException(status_code=500, detail="未找到 config.yml，无法启动世界书工坊 AI")
    try:
        result = WorldbookWorkshopAgent(global_ai_engine).respond(workshop, payload.message.strip(), payload.mode, commit_changes=payload.commit_changes)
        workshop.save_session(WORKSHOP_DIR)
        return {**_payload(workshop), **result}
    except (WorkshopError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/workshops/{workshop_id}/pending/{operation_id}/approve")
def approve_operation(workshop_id: str, operation_id: str):
    workshop = _get(workshop_id)
    try:
        workshop.approve(operation_id)
        workshop.save_session(WORKSHOP_DIR)
        return _payload(workshop)
    except WorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/workshops/{workshop_id}/pending/{operation_id}")
def reject_operation(workshop_id: str, operation_id: str):
    workshop = _get(workshop_id)
    try:
        workshop.reject(operation_id)
        workshop.save_session(WORKSHOP_DIR)
        return _payload(workshop)
    except WorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/workshops/{workshop_id}/undo")
def undo_workshop(workshop_id: str):
    workshop = _get(workshop_id)
    try:
        workshop.undo()
        workshop.save_session(WORKSHOP_DIR)
        return _payload(workshop)
    except WorkshopError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/workshops/{workshop_id}/publish")
def publish_workshop(workshop_id: str, payload: PublishRequest):
    workshop = _get(workshop_id)
    target = workshop.target_path
    if payload.worldbook_name:
        safe_name = "".join(char for char in payload.worldbook_name if char.isalnum() or char in " _-").strip()
        if not safe_name:
            raise HTTPException(status_code=400, detail="世界书名称无效")
        workshop.draft["name"] = payload.worldbook_name.strip()
        target = Path(WORLD_DIR) / f"{safe_name}.yml"
    elif target.name.endswith(".template.yml") or workshop.draft.get("is_template") is True:
        raise HTTPException(status_code=400, detail="模板世界书必须另存为个人世界书")
    workshop.publish(target)
    workshop.target_path = target
    workshop.save_session(WORKSHOP_DIR)
    return {**_payload(workshop), "published_path": str(target)}
