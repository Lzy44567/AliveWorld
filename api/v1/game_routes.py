# api/v1/game_routes.py
import os, yaml, uuid, glob
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.game_session import GameSession
from core.ai_engine import AIEngine
# 🚀 修复点：彻底导入了所有的工具函数！
from utils.file_io import BASE_DIR, CHAR_DIR, STYLE_DIR, WORLD_DIR, get_all_saves, save_game_data

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
    style_name: str = "默认 (无)"
    worldbook_name: str = "无界域 (暂不加载)"
    save_name: str = "未命名冒险" # 🚀 新增：接收前端输入的存档名

class ActionRequest(BaseModel):
    action: str
    override_style: Optional[str] = None
    override_worldbook: Optional[str] = None

class LoadRequest(BaseModel):
    save_name: str

# ============ 辅助函数 ============
def load_yaml_by_name(directory, name):
    if name in ["默认 (无)", "无界域 (暂不加载)", ""]: return {}
    for f in glob.glob(os.path.join(directory, "*.yml")):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and data.get('name') == name: 
                    return data
        except: pass
    return {}

# ============ API：启动新游戏 ============
@router.post("/start")
def start_game(payload: StartRequest):
    if not global_ai_engine:
        raise HTTPException(status_code=500, detail="未找到 config.yml")
        
    session_id = str(uuid.uuid4())
    # 传入前端定义的存档名
    game = GameSession(global_ai_engine, payload.save_name)
    
    char_data = {"name": "冒险者", "initial_hp": 100, "initial_mana": 100, "description": "无名之辈。"}
    all_chars = glob.glob(os.path.join(CHAR_DIR, "*.yml"))
    if all_chars:
        with open(all_chars[0], 'r', encoding='utf-8') as f: 
            char_data = yaml.safe_load(f)

    style_data = load_yaml_by_name(STYLE_DIR, payload.style_name)
    world_data = load_yaml_by_name(WORLD_DIR, payload.worldbook_name)
    
    style_content = style_data.get('content', '')
    opening = world_data.get('starting_scene', '') + "\n\n" + char_data.get('starting_scene', '你在一片混沌中苏醒...')
    
    game.start_new_game(char_data, style_content, world_data, opening.strip())
    active_sessions[session_id] = game
    
    # 🚀 自动落盘
    save_game_data(game.save_name, game.export_save_data())
    
    return {"session_id": session_id, "chat_messages": game.history["chat_messages"], "state": game.state}

# ============ 🚀 API：载入旧存档 ============
@router.post("/load")
def load_game(payload: LoadRequest):
    saves = get_all_saves()
    if payload.save_name not in saves:
        raise HTTPException(status_code=404, detail="存档已损坏或不存在")
        
    save_data = saves[payload.save_name]
    session_id = str(uuid.uuid4())
    
    # 恢复 V1 引擎状态
    game = GameSession(global_ai_engine, payload.save_name)
    game.load_save_data(save_data)
    active_sessions[session_id] = game
    
    return {
        "session_id": session_id,
        "chat_messages": game.history["chat_messages"],
        "state": game.state,
        "worldbook_name": "界域已恢复", 
        "style_name": "文风已恢复"
    }

# ============ API：执行回合 ============
@router.post("/{session_id}/action")
def process_turn(session_id: str, payload: ActionRequest):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    
    if payload.override_style and payload.override_style != "默认 (无)":
        game.style_info = load_yaml_by_name(STYLE_DIR, payload.override_style).get('content', '')
        
    history_len = len(game.history["chat_messages"])
    result = game.process_turn(payload.action)
    
    if result and result.get('error'): raise HTTPException(status_code=500, detail="推演失败")
        
    # 🚀 自动落盘
    save_game_data(game.save_name, game.export_save_data())
        
    return {"chat_messages": game.history["chat_messages"][history_len:], "state": game.state, "is_game_over": game.is_game_over}

# ============ API：撤回上回合 ============
@router.post("/{session_id}/undo")
def undo_turn(session_id: str):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    
    if not game.rollback(): raise HTTPException(status_code=400, detail="无法撤回")
    
    # 🚀 自动落盘
    save_game_data(game.save_name, game.export_save_data())
        
    return {"chat_messages": game.history["chat_messages"], "state": game.state}

# ============ API：重试本回合 ============
@router.post("/{session_id}/retry")
def retry_turn(session_id: str, payload: ActionRequest):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    
    if not game.rollback(): raise HTTPException(status_code=400, detail="无历史")
    
    if payload.override_style and payload.override_style != "默认 (无)":
        game.style_info = load_yaml_by_name(STYLE_DIR, payload.override_style).get('content', '')
        
    result = game.process_turn(payload.action)
    if result and result.get('error'): raise HTTPException(status_code=500, detail="推演失败")
    
    # 🚀 自动落盘
    save_game_data(game.save_name, game.export_save_data())
    
    return {"full_chat": game.history["chat_messages"], "state": game.state}