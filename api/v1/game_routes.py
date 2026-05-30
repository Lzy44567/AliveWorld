# api/v1/game_routes.py
# 100% 完整物理读写底稿 (请直接覆盖原文件)

import os
import yaml
import uuid
import glob
import shutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from core.game_session import GameSession
from core.ai_engine import AIEngine
from utils.file_io import BASE_DIR, DATA_DIR, init_save_folder, get_all_saves, save_game_data

router = APIRouter()
active_sessions: dict[str, GameSession] = {}

config_path = os.path.join(BASE_DIR, 'config.yml')
if os.path.exists(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        global_ai_engine = AIEngine(yaml.safe_load(f))
else:
    global_ai_engine = None

# ============ 数据请求结构 ============
class StartRequest(BaseModel):
    save_name: str = "未命名冒险"
    description: str = "" # 故事简述

class ActionRequest(BaseModel):
    action: str
    plot_compass: Optional[str] = "" # 🚀 接收前端传递的剧本导向

class LoadRequest(BaseModel):
    save_name: str

class PullAssetRequest(BaseModel):
    asset_type: str
    asset_name: str

class LocalAssetUpdatePayload(BaseModel):
    parsed_data: Dict[str, Any]

DIR_MAP = {
    "worldbooks": os.path.join(DATA_DIR, 'worldbooks'), 
    "styles": os.path.join(DATA_DIR, 'styles'), 
    "characters": os.path.join(DATA_DIR, 'characters'), 
    "entities": os.path.join(DATA_DIR, 'entities')
}

@router.post("/start")
def start_game(payload: StartRequest):
    if not global_ai_engine:
        raise HTTPException(status_code=500, detail="未找到 config.yml")
        
    session_id = str(uuid.uuid4())
    save_dir_path = init_save_folder(payload.save_name)
    game = GameSession(global_ai_engine, payload.save_name, save_dir_path=save_dir_path)
    
    opening = "【时间线已建立】\n"
    if payload.description:
        opening += f"宇宙法则主导向被设定为：{payload.description}\n"
    opening += "当前世界犹如一张白纸。你可以随时从右侧“万象资产”中拉取角色、世界书或文风进入本局..."
    
    game.start_new_game(description=payload.description, opening=opening.strip())
    active_sessions[session_id] = game
    save_game_data(game.save_dir_path, game.export_save_data())
    
    return {"session_id": session_id, "chat_messages": game.history["chat_messages"], "state": game.state, "description": game.description}

@router.post("/load")
def load_game(payload: LoadRequest):
    saves = get_all_saves()
    if payload.save_name not in saves:
        raise HTTPException(status_code=404, detail="存档已损坏或不存在")
        
    save_data = saves[payload.save_name]
    session_id = str(uuid.uuid4())
    
    save_dir_path = save_data.get('save_dir_path', '')
    game = GameSession(global_ai_engine, payload.save_name, save_dir_path=save_dir_path)
    game.load_save_data(save_data)
    active_sessions[session_id] = game
    
    return {
        "session_id": session_id,
        "chat_messages": game.history["chat_messages"],
        "state": game.state,
        "description": game.description
    }

@router.post("/{session_id}/action")
def process_turn(session_id: str, payload: ActionRequest):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    
    # 🚀 实时更新剧情主导向
    if payload.plot_compass is not None:
        game.description = payload.plot_compass
        
    history_len = len(game.history["chat_messages"])
    result = game.process_turn(payload.action)
    
    if result and result.get('error'): raise HTTPException(status_code=500, detail="推演失败")
    save_game_data(game.save_dir_path, game.export_save_data())
        
    return {"chat_messages": game.history["chat_messages"][history_len:], "state": game.state, "is_game_over": game.is_game_over}

@router.post("/{session_id}/undo")
def undo_turn(session_id: str):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    if not game.rollback(): raise HTTPException(status_code=400, detail="无法撤回")
    save_game_data(game.save_dir_path, game.export_save_data())
    return {"chat_messages": game.history["chat_messages"], "state": game.state}

@router.post("/{session_id}/retry")
def retry_turn(session_id: str, payload: ActionRequest):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    if not game.rollback(): raise HTTPException(status_code=400, detail="无历史")
    
    if payload.plot_compass is not None:
        game.description = payload.plot_compass
        
    result = game.process_turn(payload.action)
    if result and result.get('error'): raise HTTPException(status_code=500, detail="推演失败")
    save_game_data(game.save_dir_path, game.export_save_data())
    return {"full_chat": game.history["chat_messages"], "state": game.state}

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