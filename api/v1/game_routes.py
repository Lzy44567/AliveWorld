# api/v1/game_routes.py
import os
import yaml
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from core.game_session import GameSession
from core.ai_engine import AIEngine
from core.session_manager import active_sessions
from core.story_settings import normalize_story_settings
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
    world_premise: Optional[str] = None
    story_settings: Dict[str, Any] = Field(default_factory=dict)

class ActionRequest(BaseModel):
    action: str
    plot_compass: Optional[str] = None

class EntityRuntimeRequest(BaseModel):
    entities_enabled: Optional[bool] = None

class StoryConfigPayload(BaseModel):
    world_premise: str = ""
    plot_compass: str = ""
    story_settings: Dict[str, Any] = Field(default_factory=dict)

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
    game = GameSession(global_ai_engine, payload.save_name, save_dir_path=save_dir_path, story_settings=payload.story_settings)
    world_premise = payload.world_premise if payload.world_premise is not None else payload.description
    
    opening = "【时间线已建立】\n"
    if world_premise: opening += f"宇宙法则主导向被设定为：{world_premise}\n"
    opening += "当前世界犹如一张白纸。你可以随时从右侧“万象资产”中拉取角色、世界书或文风进入本局..."
    
    game.start_new_game(world_premise=world_premise, opening=opening.strip())
    active_sessions[session_id] = game
    save_game_data(game.save_dir_path, game.export_save_data())
    return _session_payload(session_id, game)

@router.post("/load")
def load_game(payload: LoadRequest):
    saves = get_all_saves()
    if payload.save_name not in saves: raise HTTPException(status_code=404, detail="存档已损坏或不存在")
    save_data = saves[payload.save_name]
    session_id = str(uuid.uuid4())
    
    game = GameSession(global_ai_engine, payload.save_name, save_dir_path=save_data.get('save_dir_path', ''))
    game.load_save_data(save_data)
    active_sessions[session_id] = game
    return _session_payload(session_id, game)

@router.post("/{session_id}/action")
def process_turn(session_id: str, payload: ActionRequest):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    if payload.plot_compass is not None: game.plot_compass = payload.plot_compass
        
    history_len = len(game.history["chat_messages"])
    result = game.process_turn(payload.action)
    if result and result.get('error'): raise HTTPException(status_code=502, detail=result.get("message", "推演失败，本回合未保存。"))
    
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
    if payload.plot_compass is not None: game.plot_compass = payload.plot_compass
        
    result = game.process_turn(payload.action)
    if result and result.get('error'): raise HTTPException(status_code=502, detail=result.get("message", "推演失败，本回合未保存。"))
    save_game_data(game.save_dir_path, game.export_save_data())
    return {"full_chat": game.history["chat_messages"], "state": game.state}

# 🚀 核心：重掷未来专用接口
@router.post("/{session_id}/reroll")
def reroll_turn(session_id: str, payload: EntityRuntimeRequest):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    if payload.entities_enabled is not None:
        game.story_settings["entitiesEnabled"] = payload.entities_enabled
    res = game.reroll_turn()
    if not res or res.get("error"): raise HTTPException(status_code=400, detail="无法重掷")
    save_game_data(game.save_dir_path, game.export_save_data())
    return res

@router.post("/{session_id}/story_config")
def update_story_config(session_id: str, payload: StoryConfigPayload):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    game.world_premise = payload.world_premise
    game.plot_compass = payload.plot_compass
    game.story_settings = normalize_story_settings(payload.story_settings)
    save_game_data(game.save_dir_path, game.export_save_data())
    return _story_config_payload(game)

def _story_config_payload(game):
    return {
        "world_premise": game.world_premise,
        "plot_compass": game.plot_compass,
        "story_settings": game.story_settings,
    }

def _session_payload(session_id, game):
    return {
        "session_id": session_id,
        "chat_messages": game.history["chat_messages"],
        "state": game.state,
        "description": game.world_premise,
        **_story_config_payload(game),
    }

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
