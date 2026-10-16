# api/v1/local_asset_routes.py
import os
import glob
import yaml
import shutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, StrictBool
from typing import Dict, Any

from core.session_manager import active_sessions
from utils.file_io import DATA_DIR, save_game_data
from utils.asset_catalog import resolve_asset_path
from core.worldbook import normalize_worldbook, save_worldbook_atomic, worldbook_write_guard
from core.character_asset_write import CharacterWriteError, character_revision, write_character
from core.image_generation.runtime import get_image_runtime
from core.image_generation.portrait import task_is_local_portrait
from core.image_generation.service import ImageTaskError
from core.asset_lifecycle import AssetLifecycleError, clone_yaml_asset, find_yaml_asset, normalize_asset_name, rename_yaml_asset
from core.worldbook_workshop_registry import retarget_workshops
from core.worldbook_revisions import reconcile_capture_history
from core.worldbook_review import review_proposals, WorldbookReviewError
from core.worldbook import worldbook_revision, WorldbookRevisionConflict
from core.session_manager import mutation_guard, save_identity, MutationBusyError
from core.asset_workshop_registry import retarget_asset_workshops
from core.entities import Entity
from core.world_packages.provenance import refresh_local_instance_id, system_tags_from_asset

router = APIRouter()

DIR_MAP = {
    "worldbooks": os.path.join(DATA_DIR, 'worldbooks'), 
    "styles": os.path.join(DATA_DIR, 'styles'), 
    "characters": os.path.join(DATA_DIR, 'characters'), 
    "entities": os.path.join(DATA_DIR, 'entities')
}

class PullAssetRequest(BaseModel):
    asset_type: str
    asset_name: str

class LocalAssetUpdatePayload(BaseModel):
    parsed_data: Dict[str, Any]
    overwrite: bool = True
    expected_revision: str | None = None

class LocalAssetLifecyclePayload(BaseModel):
    new_name: str

class CaptureReviewDecision(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    accept: StrictBool

class CaptureReviewRequest(BaseModel):
    expected_revision: str
    decisions: list[CaptureReviewDecision] = Field(min_length=1, max_length=100)

@router.post('/{session_id}/worldbooks/{asset_name}/review')
def review_worldbook_capture(session_id: str, asset_name: str, payload: CaptureReviewRequest):
    game = active_sessions.get(session_id)
    if not game or not game.save_dir_path:
        raise HTTPException(status_code=404, detail='会话失效')
    try:
        with mutation_guard('story', save_identity(game.save_dir_path)):
            path = find_yaml_asset(os.path.join(game.save_dir_path, 'worldbooks'), asset_name)
            if path is None:
                raise HTTPException(status_code=404, detail='局内世界书不存在')
            with worldbook_write_guard(path):
                raw = path.read_bytes()
                if worldbook_revision(raw) != payload.expected_revision:
                    raise WorldbookReviewError('世界书已更新，请刷新后重试')
                book = normalize_worldbook(yaml.safe_load(raw.decode('utf-8')))
                reviewed = review_proposals(book, [d.model_dump() for d in payload.decisions], game.history.get('story_turns', []))
                save_worldbook_atomic(path, reviewed, expected_revision=payload.expected_revision)
                reviewed['edit_revision'] = worldbook_revision(path.read_bytes())
                return {'status': 'success', 'book': reviewed}
    except (WorldbookReviewError, WorldbookRevisionConflict, MutationBusyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AssetLifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError:
        raise HTTPException(status_code=500, detail='世界书保存失败，原内容保持不变') from None

@router.get("/{session_id}/local_assets")
def get_local_assets(session_id: str):
    game = active_sessions.get(session_id)
    if not game or not game.save_dir_path: raise HTTPException(status_code=404, detail="会话失效")
    
    def scan_local_dir(sub_dir):
        items = []
        target_path = os.path.join(game.save_dir_path, sub_dir)
        if not os.path.exists(target_path): return items
        
        for f in glob.glob(os.path.join(target_path, '*.yml')):
            try:
                with open(f, 'rb') as file:
                    raw = file.read()
                    data = yaml.safe_load(raw.decode('utf-8'))
                    if data:
                        if sub_dir == 'worldbooks' and data.get('capture_history'):
                            data, _ = reconcile_capture_history(data, game.history.get('story_turns', []))
                        if sub_dir == 'worldbooks':
                            data['edit_revision'] = worldbook_revision(raw)
                        if sub_dir == 'characters':
                            data['edit_revision'] = character_revision(data)
                        data['is_active'] = data.get('is_active', True)
                        data['tags'] = data.get('tags', []) + ["本局独有"]
                        data['system_tags'] = system_tags_from_asset(data)
                        items.append(data)
            except: pass
        return items

    return {
        "worldbooks": scan_local_dir('worldbooks'),
        "styles": scan_local_dir('styles'),
        "characters": scan_local_dir('characters'),
        "entities": scan_local_dir('entities')
    }

@router.post("/{session_id}/pull_asset")
def pull_asset(session_id: str, payload: PullAssetRequest):
    game = active_sessions.get(session_id)
    if not game or not game.save_dir_path: raise HTTPException(status_code=404, detail="会话失效")
    if payload.asset_type not in DIR_MAP: raise HTTPException(status_code=400, detail="类型错误")
    
    global_file = resolve_asset_path(payload.asset_type, payload.asset_name)
    if not global_file: raise HTTPException(status_code=404, detail="全局资源不存在")
    
    local_dir = os.path.join(game.save_dir_path, payload.asset_type)
    os.makedirs(local_dir, exist_ok=True)
    local_file = os.path.join(local_dir, f"{payload.asset_name}.yml")
    
    try:
        data = yaml.safe_load(global_file.read_text(encoding='utf-8')) or {}
        if payload.asset_type == "worldbooks":
            if isinstance(data, dict):
                refresh_local_instance_id(data)
            save_worldbook_atomic(local_file, data)
        elif isinstance(data, dict) and refresh_local_instance_id(data):
            with open(local_file, 'w', encoding='utf-8') as file:
                yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)
        else:
            shutil.copy2(global_file, local_file)
        return {"status": "success", "message": f"{payload.asset_name} 降临成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"拉取失败: {str(e)}")

@router.post("/{session_id}/assets/{asset_type}/{asset_name}")
def update_local_asset(session_id: str, asset_type: str, asset_name: str, payload: LocalAssetUpdatePayload):
    game = active_sessions.get(session_id)
    if not game or not game.save_dir_path: raise HTTPException(status_code=404, detail="会话失效")
    
    local_dir = os.path.join(game.save_dir_path, asset_type)
    os.makedirs(local_dir, exist_ok=True)
    local_file = os.path.join(local_dir, f"{asset_name}.yml")
    if asset_type == 'worldbooks':
        try:
            with mutation_guard('story', save_identity(game.save_dir_path)), worldbook_write_guard(local_file):
                from pathlib import Path
                path = Path(local_file)
                existing = {}
                if path.exists():
                    if not payload.overwrite:
                        raise WorldbookReviewError('本局已存在同名世界书')
                    raw = path.read_bytes()
                    if payload.expected_revision is not None and worldbook_revision(raw) != payload.expected_revision:
                        raise WorldbookReviewError('世界书已更新，请刷新后再保存，避免覆盖新设定')
                    existing, _ = reconcile_capture_history(normalize_worldbook(yaml.safe_load(raw.decode('utf-8'))), game.history.get('story_turns', []))
                incoming = {k: v for k, v in payload.parsed_data.items() if k not in {'capture_history', 'capture_reviews', 'edit_revision'}}
                save_worldbook_atomic(path, {**existing, **incoming}, expected_revision=payload.expected_revision)
                return {'status': 'success', 'revision': worldbook_revision(path.read_bytes())}
        except (WorldbookReviewError, WorldbookRevisionConflict, MutationBusyError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except OSError:
            raise HTTPException(status_code=500, detail='世界书保存失败，原内容保持不变') from None
    if asset_type == 'characters':
        try:
            output = write_character(local_file, dict(payload.parsed_data), expected_revision=payload.expected_revision, overwrite=payload.overwrite)
            return {'status': 'success', 'revision': character_revision(output)}
        except CharacterWriteError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (OSError, ValueError, yaml.YAMLError):
            raise HTTPException(status_code=500, detail='角色卡保存失败，原文件保持不变') from None
    if os.path.exists(local_file) and not payload.overwrite:
        raise HTTPException(
            status_code=409,
            detail=f"本局已存在同名资产“{asset_name}”，请更换名称",
        )
    
    try:
        existing_data = {}
        if os.path.exists(local_file):
            with open(local_file, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f) or {}
                if isinstance(loaded, dict): existing_data = loaded
        parsed_data = {**existing_data, **dict(payload.parsed_data)}
        if asset_type == "worldbooks":
            parsed_data = normalize_worldbook(parsed_data)
        if asset_type == "entities":
            identity = Entity.from_dict(existing_data).id if existing_data else Entity(asset_name).id
            parsed_data['id'] = identity
            parsed_data["influence_refs"] = game.undercurrent.causal_ledger.refs_for_entity(asset_name, identity)
        if asset_type == "worldbooks":
            save_worldbook_atomic(local_file, parsed_data)
        else:
            with open(local_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(parsed_data, f, allow_unicode=True, sort_keys=False)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"局内资源保存失败: {str(e)}")

@router.delete("/{session_id}/assets/{asset_type}/{asset_name}")
def delete_local_asset(session_id: str, asset_type: str, asset_name: str):
    game = active_sessions.get(session_id)
    if not game or not game.save_dir_path: raise HTTPException(status_code=404, detail="会话失效")
    
    local_file = os.path.join(game.save_dir_path, asset_type, f"{asset_name}.yml")
    if os.path.exists(local_file):
        try:
            portrait_task_id = ""
            if asset_type == "characters":
                with open(local_file, 'r', encoding='utf-8') as file:
                    character = yaml.safe_load(file) or {}
                portrait_task_id = str((character.get("portrait") or {}).get("task_id", ""))
            if asset_type == "entities":
                removed = next((entity for entity in game.undercurrent.entities if entity.name == asset_name), None)
                result = game.undercurrent.causal_ledger.handle_source_death(asset_name, removed.id if removed else None)
                game.undercurrent.entities = [entity for entity in game.undercurrent.entities if entity.name != asset_name]
                game.undercurrent.sync_influence_refs()
                save_game_data(game.save_dir_path, game.export_save_data())
            if asset_type == "worldbooks":
                with worldbook_write_guard(local_file):
                    os.remove(local_file)
            else:
                os.remove(local_file)
            portrait_deleted = False
            if portrait_task_id and not task_is_local_portrait(game.save_dir_path, portrait_task_id):
                runtime = get_image_runtime(game.save_dir_path)
                if runtime.service.repository.get(portrait_task_id):
                    try:
                        runtime.service.delete(portrait_task_id)
                        portrait_deleted = True
                    except (ImageTaskError, ValueError, OSError):
                        # A generated portrait should be terminal. If a legacy task is not,
                        # keep its files rather than turning a successful card deletion into 500.
                        portrait_deleted = False
            return {
                "status": "success",
                "deleted_portrait": portrait_deleted,
                "released_influences": [item.id for item in result["released"]] if asset_type == "entities" else [],
                "removed_influences": [item.id for item in result["removed"]] if asset_type == "entities" else [],
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail="无法删除本地副本")
    raise HTTPException(status_code=404, detail="本局专属库未找到此文件")

def _refresh_after_lifecycle(game, asset_type, old_name="", new_name=""):
    if asset_type == "entities":
        if old_name and new_name:
            for influence in game.undercurrent.causal_ledger.influences:
                for link in influence.source_links:
                    if link.get("entity") == old_name:
                        link["entity"] = new_name
        game.undercurrent.entities = game.entity_repository.load()
        game.undercurrent.sync_influence_refs()
        game.entity_repository.synchronize(game.undercurrent.entities)
    save_game_data(game.save_dir_path, game.export_save_data())

@router.post("/{session_id}/assets/{asset_type}/{asset_name}/clone")
def clone_local_asset(session_id: str, asset_type: str, asset_name: str, payload: LocalAssetLifecyclePayload):
    game = active_sessions.get(session_id)
    if not game or not game.save_dir_path:
        raise HTTPException(status_code=404, detail="会话失效")
    if asset_type not in DIR_MAP:
        raise HTTPException(status_code=400, detail="未知的资产类型")
    local_dir = os.path.join(game.save_dir_path, asset_type)
    try:
        new_name = normalize_asset_name(payload.new_name)
        target = clone_yaml_asset(local_dir, asset_name, new_name, worldbook=asset_type == "worldbooks")
        _refresh_after_lifecycle(game, asset_type)
        return {"status": "success", "name": new_name, "path": str(target)}
    except AssetLifecycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.post("/{session_id}/assets/{asset_type}/{asset_name}/rename")
def rename_local_asset(session_id: str, asset_type: str, asset_name: str, payload: LocalAssetLifecyclePayload):
    game = active_sessions.get(session_id)
    if not game or not game.save_dir_path:
        raise HTTPException(status_code=404, detail="会话失效")
    if asset_type not in DIR_MAP:
        raise HTTPException(status_code=400, detail="未知的资产类型")
    local_dir = os.path.join(game.save_dir_path, asset_type)
    try:
        new_name = normalize_asset_name(payload.new_name)
        source = find_yaml_asset(local_dir, asset_name)
        target = rename_yaml_asset(local_dir, asset_name, new_name, worldbook=asset_type == "worldbooks")
        if asset_type == "worldbooks" and source:
            retarget_workshops(source, target)
        elif source:
            retarget_asset_workshops(source, target)
        _refresh_after_lifecycle(game, asset_type, asset_name, new_name)
        return {"status": "success", "name": new_name, "path": str(target)}
    except AssetLifecycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
