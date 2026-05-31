# api/v1/local_asset_routes.py
import os
import glob
import yaml
import shutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from core.session_manager import active_sessions
from utils.file_io import DATA_DIR

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
    
    global_file = os.path.join(DIR_MAP[payload.asset_type], f"{payload.asset_name}.yml")
    if not os.path.exists(global_file): raise HTTPException(status_code=404, detail="全局资源不存在")
    
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
        with open(local_file, 'w', encoding='utf-8') as f:
            yaml.safe_dump(payload.parsed_data, f, allow_unicode=True, sort_keys=False)
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
            os.remove(local_file)
            return {"status": "success"}
        except Exception as e:
            raise HTTPException(status_code=500, detail="无法删除本地副本")
    raise HTTPException(status_code=404, detail="本局专属库未找到此文件")