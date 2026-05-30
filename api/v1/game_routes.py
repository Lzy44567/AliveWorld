# api/v1/game_routes.py
# 100% 完整物理读写底稿 (请直接覆盖原文件)

import os
import yaml
import uuid
import glob
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.game_session import GameSession
from core.ai_engine import AIEngine
from utils.file_io import BASE_DIR, CHAR_DIR, STYLE_DIR, WORLD_DIR, init_save_folder, get_all_saves, save_game_data

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
    character_name: str = "空白模板 (无名者)"  # 🚀 问题 3：支持角色选择扮演
    save_name: str = "未命名冒险"

class ActionRequest(BaseModel):
    action: str
    override_style: Optional[str] = None
    override_worldbook: Optional[str] = None

class LoadRequest(BaseModel):
    save_name: str

# ============ 辅助函数 ============
def load_yaml_by_name(directory, name):
    if name in ["默认 (无)", "无界域 (暂不加载)", "空白模板 (无名者)", ""]: return {}
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
    
    # 🚀 问题 2：首先初始化本故事线物理沙盒文件夹，将选中的全局卡片完全物理拷贝进沙盒
    save_dir_path = init_save_folder(
        payload.save_name, 
        global_worldbook=payload.worldbook_name, 
        global_style=payload.style_name, 
        global_char=payload.character_name
    )
    
    # 将物理路径存入 Session 对象中，后续任何状态都自动落盘至对应局内文件夹中
    game = GameSession(global_ai_engine, payload.save_name, save_dir_path=save_dir_path)
    
    # 从局部文件夹内加载卡片资源，防止全局与局内资产混淆
    local_char_dir = os.path.join(save_dir_path, 'characters')
    local_style_dir = os.path.join(save_dir_path, 'styles')
    local_world_dir = os.path.join(save_dir_path, 'worldbooks')
    
    char_data = {"name": "冒险者", "initial_hp": 100, "initial_mana": 100, "description": "无名之辈。"}
    local_chars = glob.glob(os.path.join(local_char_dir, "*.yml"))
    if local_chars:
        with open(local_chars[0], 'r', encoding='utf-8') as f: 
            char_data = yaml.safe_load(f)
            
    style_data = {}
    local_styles = glob.glob(os.path.join(local_style_dir, "*.yml"))
    if local_styles:
        with open(local_styles[0], 'r', encoding='utf-8') as f: 
            style_data = yaml.safe_load(f)

    world_data = {}
    local_worlds = glob.glob(os.path.join(local_world_dir, "*.yml"))
    if local_worlds:
        with open(local_worlds[0], 'r', encoding='utf-8') as f: 
            world_data = yaml.safe_load(f)
    
    style_content = style_data.get('content', '') if style_data else ''
    opening = world_data.get('starting_scene', '') + "\n\n" + char_data.get('starting_scene', '你在一片混沌中苏醒...')
    
    game.start_new_game(char_data, style_content, world_data, opening.strip())
    active_sessions[session_id] = game
    
    # 🚀 局内落盘：落盘至对应沙盒内
    save_game_data(game.save_dir_path, game.export_save_data())
    
    return {"session_id": session_id, "chat_messages": game.history["chat_messages"], "state": game.state}

# ============ API：载入旧存档 ============
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
        "worldbook_name": "界域已恢复", 
        "style_name": "文风已恢复"
    }

# ============ API：执行回合 ============
@router.post("/{session_id}/action")
def process_turn(session_id: str, payload: ActionRequest):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    
    if payload.override_style and payload.override_style != "默认 (无)":
        local_style_dir = os.path.join(game.save_dir_path, 'styles')
        game.style_info = load_yaml_by_name(local_style_dir, payload.override_style).get('content', '')
        
    history_len = len(game.history["chat_messages"])
    result = game.process_turn(payload.action)
    
    if result and result.get('error'): raise HTTPException(status_code=500, detail="推演失败")
        
    # 🚀 沙盒局部落盘
    save_game_data(game.save_dir_path, game.export_save_data())
        
    return {"chat_messages": game.history["chat_messages"][history_len:], "state": game.state, "is_game_over": game.is_game_over}

# ============ API：撤回上回合 ============
@router.post("/{session_id}/undo")
def undo_turn(session_id: str):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    
    if not game.rollback(): raise HTTPException(status_code=400, detail="无法撤回")
    
    # 🚀 沙盒局部落盘
    save_game_data(game.save_dir_path, game.export_save_data())
        
    return {"chat_messages": game.history["chat_messages"], "state": game.state}

# ============ API：重试本回合 ============
@router.post("/{session_id}/retry")
def retry_turn(session_id: str, payload: ActionRequest):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    
    if not game.rollback(): raise HTTPException(status_code=400, detail="无历史")
    
    if payload.override_style and payload.override_style != "默认 (无)":
        local_style_dir = os.path.join(game.save_dir_path, 'styles')
        game.style_info = load_yaml_by_name(local_style_dir, payload.override_style).get('content', '')
        
    result = game.process_turn(payload.action)
    if result and result.get('error'): raise HTTPException(status_code=500, detail="推演失败")
    
    # 🚀 沙盒局部落盘
    save_game_data(game.save_dir_path, game.export_save_data())
    
    return {"full_chat": game.history["chat_messages"], "state": game.state}

# ============ API：获取局内专属运行时切片 (问题 4 解决方案) ============
@router.get("/{session_id}/local_assets")
def get_local_assets(session_id: str):
    game = active_sessions.get(session_id)
    if not game: 
        raise HTTPException(status_code=404, detail="会话失效")
    
    local_worldbook = {
        "name": "本局世界书",
        "tags": ["本局专属", "动态设定"],
        "desc": game.world_info_base[:120] + "..." if game.world_info_base else "无常驻世界法则",
        "global_setting": game.world_info_base,
        "starting_scene": "",
        "entries": game.world_entries
    }
    
    local_character = {
        "name": game.state.get("player_name", "本局玩家角色"),
        "tags": ["主角"],
        "desc": game.char_info if game.char_info else "当前游玩的初始主角设定。",
        "starting_scene": ""
    }
    
    local_style = {
        "name": "本局文风卡",
        "tags": ["本局专属"],
        "desc": game.style_info[:120] + "..." if game.style_info else "使用全局默认推演风格",
        "content": game.style_info
    }
    
    local_entities = []
    for ent in game.undercurrent.entities:
        local_entities.append({
            "name": ent.name,
            "tags": ["暗流势力"],
            "desc": f"动机: {ent.goal} (处于隐蔽运作中)",
            "motive": ent.goal,
            "status": "潜伏中"
        })
        
    return {
        "worldbooks": [local_worldbook] if game.world_info_base else [],
        "characters": [local_character],
        "styles": [local_style] if game.style_info else [],
        "entities": local_entities
    }