# api/v1/local_asset_routes.py
import os
import glob
import yaml
import shutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from core.session_manager import active_sessions
from utils.file_io import DATA_DIR, save_game_data
from utils.asset_catalog import resolve_asset_path
from core.worldbook import normalize_worldbook, save_worldbook_atomic
from core.image_generation.runtime import get_image_runtime
from core.image_generation.portrait import task_is_local_portrait
from core.image_generation.service import ImageTaskError

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
                with open(f, 'r', encoding='utf-8') as file:
                    data = yaml.safe_load(file)
                    if data:
                        data['is_active'] = data.get('is_active', True)
                        data['tags'] = data.get('tags', []) + ["本局独有"]
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
            parsed_data["influence_refs"] = game.undercurrent.causal_ledger.refs_for_entity(asset_name)
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
                result = game.undercurrent.causal_ledger.handle_source_death(asset_name)
                game.undercurrent.entities = [entity for entity in game.undercurrent.entities if entity.name != asset_name]
                game.undercurrent.sync_influence_refs()
                save_game_data(game.save_dir_path, game.export_save_data())
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
