# api/v1/game_routes.py
import os
import yaml
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from core.game_session import GameSession
from core.ai_engine import AIEngine
from core.session_manager import active_sessions
from utils.file_io import BASE_DIR, init_save_folder, get_all_saves, save_game_data

router = APIRouter()

config_path = os.path.join(BASE_DIR, 'config.yml')
if os.path.exists(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        global_ai_engine = AIEngine(yaml.safe_load(f))
else:
    global_ai_engine = None

class StartRequest(BaseModel):
    save_name: str = "未命名冒险"
    description: str = ""

class ActionRequest(BaseModel):
    action: str
    plot_compass: Optional[str] = ""
    entities_enabled: bool = True

class EntityRuntimeRequest(BaseModel):
    entities_enabled: bool = True

class LoadRequest(BaseModel):
    save_name: str

class SystemConfigPayload(BaseModel):
    apiKey: str = ""
    apiBaseUrl: str = "https://api.openai.com/v1"
    model: str = "gpt-3.5-turbo"
    imageApiUrl: str = ""

@router.post("/start")
def start_game(payload: StartRequest):
    if not global_ai_engine: raise HTTPException(status_code=500, detail="未找到 config.yml")
    session_id = str(uuid.uuid4())
    save_dir_path = init_save_folder(payload.save_name)
    game = GameSession(global_ai_engine, payload.save_name, save_dir_path=save_dir_path)
    
    opening = "【时间线已建立】\n"
    if payload.description: opening += f"宇宙法则主导向被设定为：{payload.description}\n"
    opening += "当前世界犹如一张白纸。你可以随时从右侧“万象资产”中拉取角色、世界书或文风进入本局..."
    
    game.start_new_game(description=payload.description, opening=opening.strip())
    active_sessions[session_id] = game
    save_game_data(game.save_dir_path, game.export_save_data())
    return {"session_id": session_id, "chat_messages": game.history["chat_messages"], "state": game.state, "description": game.description}

@router.post("/load")
def load_game(payload: LoadRequest):
    saves = get_all_saves()
    if payload.save_name not in saves: raise HTTPException(status_code=404, detail="存档已损坏或不存在")
    save_data = saves[payload.save_name]
    session_id = str(uuid.uuid4())
    
    game = GameSession(global_ai_engine, payload.save_name, save_dir_path=save_data.get('save_dir_path', ''))
    game.load_save_data(save_data)
    active_sessions[session_id] = game
    return {"session_id": session_id, "chat_messages": game.history["chat_messages"], "state": game.state, "description": game.description}

@router.post("/{session_id}/action")
def process_turn(session_id: str, payload: ActionRequest):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    if payload.plot_compass is not None: game.description = payload.plot_compass
        
    history_len = len(game.history["chat_messages"])
    result = game.process_turn(payload.action, entities_enabled=payload.entities_enabled)
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
    if payload.plot_compass is not None: game.description = payload.plot_compass
        
    result = game.process_turn(payload.action, entities_enabled=payload.entities_enabled)
    if result and result.get('error'): raise HTTPException(status_code=500, detail="推演失败")
    save_game_data(game.save_dir_path, game.export_save_data())
    return {"full_chat": game.history["chat_messages"], "state": game.state}

# 🚀 核心：重掷未来专用接口
@router.post("/{session_id}/reroll")
def reroll_turn(session_id: str, payload: EntityRuntimeRequest):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    game.entities_enabled = payload.entities_enabled
    res = game.reroll_turn()
    if not res or res.get("error"): raise HTTPException(status_code=400, detail="无法重掷")
    save_game_data(game.save_dir_path, game.export_save_data())
    return res

@router.get("/system_config")
def get_system_config():
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                return { "apiKey": data.get("api_key", ""), "apiBaseUrl": data.get("base_url", ""), "model": data.get("model", "") }
        except: pass
    return {}

@router.post("/system_config")
def update_system_config(payload: SystemConfigPayload):
    config_data = { "api_key": payload.apiKey, "base_url": payload.apiBaseUrl, "model": payload.model, "image_api_url": payload.imageApiUrl }
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config_data, f, allow_unicode=True, sort_keys=False)
    
    global global_ai_engine
    global_ai_engine = AIEngine(config_data)
    for session in active_sessions.values(): session.ai_engine = global_ai_engine
    return {"status": "success"}
