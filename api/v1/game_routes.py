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
from core.asset_lifecycle import AssetLifecycleError, normalize_asset_name
from utils.file_io import init_save_folder, get_all_saves, save_game_data
from utils.runtime_paths import PATHS

router = APIRouter()

config_path = str(PATHS.config_file)


def _context_limit(value):
    try:
        return max(8192, int(value or 32768))
    except (TypeError, ValueError):
        return 32768


def _read_system_config():
    if not os.path.exists(config_path):
        return {}
    with open(config_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file) or {}


def _memory_runtime(config, fallback_engine):
    memory_config = {"context_limit": _context_limit(config.get("memory_context_limit", 32768))}
    if not fallback_engine:
        return None, memory_config
    independent_base_url = str(config.get("memory_base_url") or "").strip()
    merged = {
        "api_key": config.get("memory_api_key") or ("not-required" if independent_base_url else config.get("api_key", "")),
        "base_url": independent_base_url or config.get("base_url", ""),
        "model": config.get("memory_model") or config.get("model", ""),
    }
    inherited = not any(config.get(key) for key in ("memory_api_key", "memory_base_url", "memory_model"))
    return (fallback_engine if inherited else AIEngine(merged)), memory_config


def _preference_runtime(config, fallback_engine):
    if not fallback_engine:
        return None
    independent_base_url = str(config.get("preference_base_url") or "").strip()
    merged = {
        "api_key": config.get("preference_api_key") or ("not-required" if independent_base_url else config.get("api_key", "")),
        "base_url": independent_base_url or config.get("base_url", ""),
        "model": config.get("preference_model") or config.get("model", ""),
    }
    inherited = not any(config.get(key) for key in ("preference_api_key", "preference_base_url", "preference_model"))
    return fallback_engine if inherited else AIEngine(merged)


_system_config = _read_system_config()
global_ai_engine = AIEngine(_system_config) if all(_system_config.get(key) for key in ("api_key", "base_url", "model")) else None
global_memory_ai_engine, global_memory_config = _memory_runtime(_system_config, global_ai_engine)
global_preference_ai_engine = _preference_runtime(_system_config, global_ai_engine)

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
    apiKey: Optional[str] = None
    apiBaseUrl: str = "https://api.openai.com/v1"
    model: str = "gpt-3.5-turbo"
    imageApiUrl: str = ""
    memoryApiKey: Optional[str] = None
    memoryApiBaseUrl: str = ""
    memoryModel: str = ""
    memoryContextLimit: Any = 32768
    preferenceApiKey: Optional[str] = None
    preferenceApiBaseUrl: str = ""
    preferenceModel: str = ""

class SecretRevealPayload(BaseModel):
    field: str

@router.post("/start")
def start_game(payload: StartRequest):
    if not global_ai_engine:
        raise HTTPException(status_code=500, detail="请先在设置中配置可用的大语言模型 API")
    try:
        save_name = normalize_asset_name(payload.save_name)
        save_dir_path = init_save_folder(save_name)
    except FileExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"已存在同名存档“{payload.save_name.strip()}”，请更换名称",
        ) from exc
    except AssetLifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session_id = str(uuid.uuid4())
    game = GameSession(
        global_ai_engine, save_name, save_dir_path=save_dir_path,
        story_settings=payload.story_settings, memory_ai_engine=global_memory_ai_engine,
        memory_config=global_memory_config,
        preference_ai_engine=global_preference_ai_engine,
    )
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
    
    game = GameSession(
        global_ai_engine, payload.save_name, save_dir_path=save_data.get('save_dir_path', ''),
        memory_ai_engine=global_memory_ai_engine, memory_config=global_memory_config,
        preference_ai_engine=global_preference_ai_engine,
    )
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
    return {"chat_messages": game.history["chat_messages"][history_len:], "state": game.state, "is_game_over": game.is_game_over, "action_suggestions": game.action_suggestions}


def _latest_player_turn(game):
    turns = game.history.get("story_turns", [])
    return next((turn for turn in reversed(turns) if str(turn.get("player", "")).strip()), None)


def _interaction_context(turn):
    if not isinstance(turn, dict):
        return ""
    turn_id = turn.get("turn_id", "未知")
    return f"关联故事回合：{turn_id}。为避免未标记的敏感正文进入偏好分析，此事件不复制玩家行动或故事内容。"


@router.post("/{session_id}/undo")
def undo_turn(session_id: str):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    previous_turn = _latest_player_turn(game)
    if not game.rollback(): raise HTTPException(status_code=400, detail="无法撤回")
    game.record_preference_interaction(
        "undo",
        "玩家撤回了刚完成的故事回合；仅能确定玩家不接受这次整体结果，具体原因未知。",
        _interaction_context(previous_turn),
        related_turn_id=previous_turn.get("turn_id") if previous_turn else None,
    )
    save_game_data(game.save_dir_path, game.export_save_data())
    return {"chat_messages": game.history["chat_messages"], "state": game.state, "action_suggestions": game.action_suggestions}

@router.post("/{session_id}/retry")
def retry_turn(session_id: str, payload: ActionRequest):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    previous_turn = _latest_player_turn(game)
    if not game.rollback(): raise HTTPException(status_code=400, detail="无历史")
    if payload.plot_compass is not None: game.plot_compass = payload.plot_compass
        
    result = game.process_turn(payload.action)
    if result and result.get('error'): raise HTTPException(status_code=502, detail=result.get("message", "推演失败，本回合未保存。"))
    game.record_preference_interaction(
        "retry",
        "玩家保留行动意图并要求重新生成该回合；原因可能是文风、内容、角色表现或单纯输出质量。",
        _interaction_context(previous_turn),
        related_turn_id=previous_turn.get("turn_id") if previous_turn else None,
    )
    save_game_data(game.save_dir_path, game.export_save_data())
    return {"full_chat": game.history["chat_messages"], "state": game.state, "action_suggestions": game.action_suggestions}

# 🚀 核心：重掷未来专用接口
@router.post("/{session_id}/reroll")
def reroll_turn(session_id: str, payload: EntityRuntimeRequest):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    previous_turn = _latest_player_turn(game)
    if payload.entities_enabled is not None:
        game.story_settings["entitiesEnabled"] = payload.entities_enabled
    res = game.reroll_turn()
    if not res or res.get("error"): raise HTTPException(status_code=400, detail="无法重掷")
    game.record_preference_interaction(
        "reroll",
        "玩家要求重新抽取未来结果；可能是不喜欢情节，也可能只是希望获得更有利的随机结果。",
        _interaction_context(previous_turn),
        related_turn_id=previous_turn.get("turn_id") if previous_turn else None,
    )
    save_game_data(game.save_dir_path, game.export_save_data())
    return res

@router.post("/{session_id}/story_config")
def update_story_config(session_id: str, payload: StoryConfigPayload):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    game.world_premise = payload.world_premise
    game.plot_compass = payload.plot_compass
    game.story_settings = normalize_story_settings(payload.story_settings)
    if not game.story_settings["aiSuggestions"]:
        game.action_suggestions = []
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
        "action_suggestions": game.action_suggestions,
        "description": game.world_premise,
        **_story_config_payload(game),
    }

@router.get("/system_config")
def get_system_config():
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                return {
                    "apiKey": "", "apiKeyConfigured": bool(data.get("api_key")),
                    "apiBaseUrl": data.get("base_url", ""), "model": data.get("model", ""),
                    "memoryApiKey": "", "memoryApiKeyConfigured": bool(data.get("memory_api_key")),
                    "memoryApiBaseUrl": data.get("memory_base_url", ""),
                    "memoryModel": data.get("memory_model", ""),
                    "memoryContextLimit": _context_limit(data.get("memory_context_limit", 32768)),
                    "preferenceApiKey": "", "preferenceApiKeyConfigured": bool(data.get("preference_api_key")),
                    "preferenceApiBaseUrl": data.get("preference_base_url", ""),
                    "preferenceModel": data.get("preference_model", ""),
                    "imageApiUrl": data.get("image_api_url", "http://127.0.0.1:8188"),
                }
        except: pass
    return {}

@router.post("/system_config/reveal-secret")
def reveal_system_config_secret(payload: SecretRevealPayload):
    field_map = {
        "apiKey": "api_key",
        "memoryApiKey": "memory_api_key",
        "preferenceApiKey": "preference_api_key",
    }
    config_key = field_map.get(payload.field)
    if not config_key:
        raise HTTPException(status_code=400, detail="不支持读取该配置字段")
    config_data = _read_system_config()
    return {"value": str(config_data.get(config_key) or "")}

@router.post("/system_config")
def update_system_config(payload: SystemConfigPayload):
    config_data = _read_system_config()
    config_data.update({
        "base_url": payload.apiBaseUrl, "model": payload.model,
        "image_api_url": payload.imageApiUrl,
        "memory_base_url": payload.memoryApiBaseUrl, "memory_model": payload.memoryModel,
        "memory_context_limit": _context_limit(payload.memoryContextLimit),
        "preference_base_url": payload.preferenceApiBaseUrl,
        "preference_model": payload.preferenceModel,
    })
    for payload_value, config_key in (
        (payload.apiKey, "api_key"),
        (payload.memoryApiKey, "memory_api_key"),
        (payload.preferenceApiKey, "preference_api_key"),
    ):
        # A blank field means “keep the secret already stored on disk”.
        # Secrets are never returned by GET and therefore cannot be round-tripped by the browser.
        if payload_value is not None and str(payload_value).strip():
            config_data[config_key] = str(payload_value).strip()
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config_data, f, allow_unicode=True, sort_keys=False)
    
    global global_ai_engine, global_memory_ai_engine, global_memory_config, global_preference_ai_engine
    global_ai_engine = (
        AIEngine(config_data)
        if all(config_data.get(key) for key in ("api_key", "base_url", "model"))
        else None
    )
    global_memory_ai_engine, global_memory_config = _memory_runtime(config_data, global_ai_engine)
    global_preference_ai_engine = _preference_runtime(config_data, global_ai_engine)
    for session in active_sessions.values():
        session.ai_engine = global_ai_engine
        session.undercurrent.ai_engine = global_ai_engine
        session.worldbook_capture.ai_engine = global_ai_engine
        session.story_memory.set_runtime(ai_engine=global_memory_ai_engine, context_limit=global_memory_config["context_limit"])
        session.preference_analysis.set_runtime(global_preference_ai_engine)
    return {"status": "success"}
