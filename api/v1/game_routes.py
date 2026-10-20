# api/v1/game_routes.py
import copy
import uuid
import shutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from core.game_session import GameSession
from core.ai_engine import AIEngine
from core.model_connections.repository import ConnectionRepository
from core.model_connections.runtime import model_runtime
from core.session_manager import (
    MutationBusyError, active_sessions, existing_session, mutation_guard,
    register_session, save_identity,
)
from core.story_settings import normalize_story_settings
from core.asset_lifecycle import AssetLifecycleError, normalize_asset_name
from core.auto_worldbook import select_capture_worldbook
from utils.file_io import init_save_folder, get_all_saves, save_game_data
from utils.runtime_paths import PATHS
from utils.sys_logger import get_logger
from api.v1.streaming import stream_response
from api.v1.generation_routes import GenerationPayload, controlled_generation
from core.generation_control import generation_commit
from core.story_start_assets import prepare_start_assets, write_start_assets

router = APIRouter()
log = get_logger()

config_path = str(PATHS.config_file)


def _context_limit(value):
    try:
        return max(8192, int(value or 32768))
    except (TypeError, ValueError):
        return 32768


def _read_system_config():
    return ConnectionRepository(config_path).read_raw()


def _bind_runtime_repository() -> None:
    expected = ConnectionRepository(config_path)
    if model_runtime.repository.path != expected.path:
        model_runtime.repository = expected
        model_runtime.snapshot = None


def _runtime_engines(*, persist_migration: bool = False):
    _bind_runtime_repository()
    model_runtime.reload(persist_migration=persist_migration)
    return {
        "story": model_runtime.engine("story"),
        "overseer": model_runtime.engine("overseer"),
        "worldbook_capture": model_runtime.engine("worldbook_capture"),
        "memory": model_runtime.engine("memory"),
        "preference": model_runtime.engine("preference"),
        "image_prompt": model_runtime.engine("image_prompt"),
        "memory_config": model_runtime.memory_config(),
    }


_engines = _runtime_engines()
global_ai_engine = _engines["story"]
global_overseer_ai_engine = _engines["overseer"]
global_worldbook_capture_ai_engine = _engines["worldbook_capture"]
global_memory_ai_engine = _engines["memory"]
global_preference_ai_engine = _engines["preference"]
global_image_prompt_ai_engine = _engines["image_prompt"]
global_memory_config = _engines["memory_config"]

class StartRequest(BaseModel):
    save_name: str = "未命名冒险"
    description: str = ""
    world_premise: Optional[str] = None
    opening: str = Field(default="", max_length=20000)
    worldbook: str = ""
    player_character: str = ""
    style: str = ""
    story_settings: Dict[str, Any] = Field(default_factory=dict)

class ActionRequest(GenerationPayload):
    action: str
    plot_compass: Optional[str] = None

class EntityRuntimeRequest(GenerationPayload):
    entities_enabled: Optional[bool] = None

class StoryConfigPayload(BaseModel):
    world_premise: str = ""
    plot_compass: str = ""
    story_settings: Dict[str, Any] = Field(default_factory=dict)

class LoadRequest(BaseModel):
    save_name: str

class SystemConfigPayload(BaseModel):
    apiKey: Optional[str] = None
    apiBaseUrl: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    imageApiUrl: Optional[str] = None
    memoryApiKey: Optional[str] = None
    memoryApiBaseUrl: str = ""
    memoryModel: str = ""
    memoryContextLimit: Any = 32768
    preferenceApiKey: Optional[str] = None
    preferenceApiBaseUrl: str = ""
    preferenceModel: str = ""

class SecretRevealPayload(BaseModel):
    field: str


def reload_system_config_runtime():
    """Reload persisted model configuration for existing and future sessions."""
    global global_ai_engine, global_overseer_ai_engine, global_worldbook_capture_ai_engine
    global global_memory_ai_engine, global_memory_config, global_preference_ai_engine
    global global_image_prompt_ai_engine
    engines = _runtime_engines(persist_migration=True)
    global_ai_engine = engines["story"]
    global_overseer_ai_engine = engines["overseer"]
    global_worldbook_capture_ai_engine = engines["worldbook_capture"]
    global_memory_ai_engine = engines["memory"]
    global_preference_ai_engine = engines["preference"]
    global_image_prompt_ai_engine = engines["image_prompt"]
    global_memory_config = engines["memory_config"]
    for session in active_sessions.values():
        session.ai_engine = global_ai_engine
        session.undercurrent.ai_engine = global_overseer_ai_engine or global_ai_engine
        session.worldbook_capture.ai_engine = global_worldbook_capture_ai_engine or global_ai_engine
        session.story_memory.set_runtime(
            ai_engine=global_memory_ai_engine or global_ai_engine,
            context_limit=global_memory_config["context_limit"],
        )
        session.preference_analysis.set_runtime(global_preference_ai_engine or global_ai_engine)
    return _read_system_config()


def _connection_error_message(error: str) -> str:
    lowered = str(error or "").lower()
    if "supported api model names" in lowered or ("400" in lowered and "model" in lowered):
        return "模型名称不受当前 API 服务支持，请核对模型名。DeepSeek 官方接口请使用 deepseek-v4-flash 或 deepseek-v4-pro。"
    if "401" in lowered or "authentication" in lowered or "invalid api key" in lowered:
        return "API Key 无效或没有访问权限。"
    if "429" in lowered or "insufficient_balance" in lowered:
        return "API 额度不足或请求过于频繁。"
    if "connection" in lowered or "timeout" in lowered or "dns" in lowered:
        return "无法连接模型服务，请检查网络、代理/VPN、DNS 与 API 地址。"
    return f"模型测试失败：{str(error or '未知错误')[:300]}"

@router.post("/start")
def start_game(payload: StartRequest):
    if not global_ai_engine:
        raise HTTPException(status_code=500, detail="请先在设置中配置可用的大语言模型 API")
    try:
        save_name = normalize_asset_name(payload.save_name)
        prepared = prepare_start_assets({
            "worldbooks": payload.worldbook, "characters": payload.player_character,
            "styles": payload.style,
        })
        save_dir_path = init_save_folder(save_name)
    except FileExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"已存在同名存档“{payload.save_name.strip()}”，请更换名称",
        ) from exc
    except AssetLifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        write_start_assets(save_dir_path, prepared)
        return start_prepared_game(
            save_name=save_name,
            save_dir_path=save_dir_path,
            world_premise=payload.world_premise if payload.world_premise is not None else payload.description,
            story_settings=payload.story_settings,
            opening=payload.opening,
        )
    except Exception:
        # init_save_folder exclusively created this directory; never remove an old save.
        shutil.rmtree(save_dir_path, ignore_errors=True)
        raise


def start_prepared_game(
    *,
    save_name: str,
    save_dir_path: str,
    world_premise: str = "",
    story_settings: dict[str, Any] | None = None,
    opening: str = "",
    initial_state: dict[str, Any] | None = None,
):
    """Start a session after a trusted caller has materialized the save directory."""
    if not global_ai_engine:
        shutil.rmtree(save_dir_path, ignore_errors=True)
        raise HTTPException(status_code=500, detail="请先在设置中配置可用的大语言模型 API")
    # A blank story still needs a save-local target for later setting capture.
    # Authored/package worldbooks take precedence and suppress this fallback.
    select_capture_worldbook(save_dir_path, create_fallback=True)
    session_id = str(uuid.uuid4())
    game = GameSession(
        global_ai_engine, save_name, save_dir_path=save_dir_path,
        story_settings=story_settings or {}, memory_ai_engine=global_memory_ai_engine,
        memory_config=global_memory_config,
        preference_ai_engine=global_preference_ai_engine,
        overseer_ai_engine=global_overseer_ai_engine,
        worldbook_capture_ai_engine=global_worldbook_capture_ai_engine,
    )
    if initial_state:
        game.state_mgr.state = copy.deepcopy(initial_state)
    game.start_new_game(world_premise=world_premise, opening=opening.strip())
    save_game_data(game.save_dir_path, game.export_save_data())
    register_session(session_id, game)
    return _session_payload(session_id, game)

@router.post("/load")
def load_game(payload: LoadRequest):
    saves = get_all_saves()
    if payload.save_name not in saves: raise HTTPException(status_code=404, detail="存档已损坏或不存在")
    save_data = saves[payload.save_name]
    runtime_save_dir = str(save_data.get("_save_dir") or "")
    if not runtime_save_dir:
        raise HTTPException(status_code=500, detail="无法确定当前存档目录")
    existing = existing_session(runtime_save_dir)
    if existing:
        try:
            with mutation_guard("story", save_identity(runtime_save_dir)):
                return _session_payload(*existing)
        except MutationBusyError as exc:
            raise HTTPException(status_code=409, detail="该故事仍在后台完成上一项操作，请稍后再次载入") from exc
    session_id = str(uuid.uuid4())
    
    game = GameSession(
        global_ai_engine, payload.save_name, save_dir_path=runtime_save_dir,
        memory_ai_engine=global_memory_ai_engine, memory_config=global_memory_config,
        preference_ai_engine=global_preference_ai_engine,
        overseer_ai_engine=global_overseer_ai_engine,
        worldbook_capture_ai_engine=global_worldbook_capture_ai_engine,
    )
    game.load_save_data(save_data, save_dir_path=runtime_save_dir)
    register_session(session_id, game)
    # Repair the stale path before the next turn, even if the player only loads
    # and immediately closes the application.
    save_game_data(game.save_dir_path, game.export_save_data())
    return _session_payload(session_id, game)


def _run_story_mutation(game, operation):
    try:
        with mutation_guard("story", save_identity(game.save_dir_path)):
            return operation()
    except MutationBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _persisted_story_mutation(game, operation):
    """Commit memory and the save file as one observable route transaction."""
    checkpoint = game.capture_transaction_state()
    try:
        result = operation()
        with generation_commit():
            save_game_data(game.save_dir_path, game.export_save_data())
    except Exception:
        try:
            game.restore_transaction_state(checkpoint)
        except Exception as restore_error:
            log.exception("故事事务失败后无法完全恢复运行时副本: %s", restore_error)
        raise

    dispatch = getattr(game, "dispatch_committed_worldbook_captures", None)
    if dispatch:
        try:
            dispatch()
        except Exception as exc:
            log.warning("正文已保存；后置捕获任务未启动: %s", exc)
    return result

@router.post("/{session_id}/action")
def process_turn(session_id: str, payload: ActionRequest):
    return _process_turn(session_id, payload)


@router.post("/{session_id}/action/stream")
def process_turn_stream(session_id: str, payload: ActionRequest):
    return stream_response(lambda emit: _process_turn(session_id, payload, on_text_delta=emit), identity=session_id)


@controlled_generation('story')
def _process_turn(session_id, payload, *, on_text_delta=None):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    def operation():
        def mutate():
            if payload.plot_compass is not None: game.plot_compass = payload.plot_compass
            history_len = len(game.history["chat_messages"])
            result = game.process_turn(payload.action, **({"on_text_delta": on_text_delta} if on_text_delta is not None else {}))
            if result and result.get('error'): raise HTTPException(status_code=502, detail=result.get("message", "推演失败，本回合未保存。"))
            return {"chat_messages": game.history["chat_messages"][history_len:], "state": game.state, "is_game_over": game.is_game_over, "action_suggestions": game.action_suggestions}
        return _persisted_story_mutation(game, mutate)
    return _run_story_mutation(game, operation)


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
    def operation():
        def mutate():
            previous_turn = _latest_player_turn(game)
            if not game.rollback(): raise HTTPException(status_code=400, detail="无法撤回")
            game.record_preference_interaction(
                "undo", "玩家撤回了刚完成的故事回合；仅能确定玩家不接受这次整体结果，具体原因未知。",
                _interaction_context(previous_turn), related_turn_id=previous_turn.get("turn_id") if previous_turn else None,
            )
            return {"chat_messages": game.history["chat_messages"], "state": game.state, "action_suggestions": game.action_suggestions}
        return _persisted_story_mutation(game, mutate)
    return _run_story_mutation(game, operation)

@router.post("/{session_id}/retry")
def retry_turn(session_id: str, payload: ActionRequest):
    return _retry_turn(session_id, payload)


@router.post("/{session_id}/retry/stream")
def retry_turn_stream(session_id: str, payload: ActionRequest):
    return stream_response(lambda emit: _retry_turn(session_id, payload, on_text_delta=emit), identity=session_id)


@controlled_generation('story')
def _retry_turn(session_id, payload, *, on_text_delta=None):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    def operation():
        def mutate():
            previous_turn = _latest_player_turn(game)
            if not game.rollback(): raise HTTPException(status_code=400, detail="无历史")
            if payload.plot_compass is not None: game.plot_compass = payload.plot_compass
            result = game.process_turn(payload.action, **({"on_text_delta": on_text_delta} if on_text_delta is not None else {}))
            if result and result.get('error'): raise HTTPException(status_code=502, detail=result.get("message", "推演失败，本回合未保存。"))
            game.record_preference_interaction(
                "retry", "玩家保留行动意图并要求重新生成该回合；原因可能是文风、内容、角色表现或单纯输出质量。",
                _interaction_context(previous_turn), related_turn_id=previous_turn.get("turn_id") if previous_turn else None,
            )
            return {"full_chat": game.history["chat_messages"], "state": game.state, "action_suggestions": game.action_suggestions}
        return _persisted_story_mutation(game, mutate)
    return _run_story_mutation(game, operation)

# 🚀 核心：重掷未来专用接口
@router.post("/{session_id}/reroll")
def reroll_turn(session_id: str, payload: EntityRuntimeRequest):
    return _reroll_turn(session_id, payload)


@router.post("/{session_id}/reroll/stream")
def reroll_turn_stream(session_id: str, payload: EntityRuntimeRequest):
    return stream_response(lambda emit: _reroll_turn(session_id, payload, on_text_delta=emit), identity=session_id)


@controlled_generation('story')
def _reroll_turn(session_id, payload, *, on_text_delta=None):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    def operation():
        def mutate():
            previous_turn = _latest_player_turn(game)
            if payload.entities_enabled is not None:
                game.story_settings["entitiesEnabled"] = payload.entities_enabled
            res = game.reroll_turn(**({"on_text_delta": on_text_delta} if on_text_delta is not None else {}))
            if not res or res.get("error"): raise HTTPException(status_code=400, detail=res.get("message", "无法重掷") if res else "无法重掷")
            game.record_preference_interaction(
                "reroll", "玩家要求重新抽取未来结果；可能是不喜欢情节，也可能只是希望获得更有利的随机结果。",
                _interaction_context(previous_turn), related_turn_id=previous_turn.get("turn_id") if previous_turn else None,
            )
            return res
        return _persisted_story_mutation(game, mutate)
    return _run_story_mutation(game, operation)

@router.post("/{session_id}/story_config")
def update_story_config(session_id: str, payload: StoryConfigPayload):
    game = active_sessions.get(session_id)
    if not game: raise HTTPException(status_code=404, detail="会话失效")
    def operation():
        game.world_premise = payload.world_premise
        game.plot_compass = payload.plot_compass
        game.story_settings = normalize_story_settings(payload.story_settings)
        game.word_limit = game.story_settings["targetStoryLength"]
        if not game.story_settings["aiSuggestions"]:
            game.action_suggestions = []
        save_game_data(game.save_dir_path, game.export_save_data())
        return _story_config_payload(game)
    return _run_story_mutation(game, operation)

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
    return ConnectionRepository(config_path).legacy_public_config()

@router.post("/system_config/reveal-secret")
def reveal_system_config_secret(payload: SecretRevealPayload):
    try:
        value = ConnectionRepository(config_path).reveal_legacy_secret(payload.field)
    except KeyError:
        raise HTTPException(status_code=400, detail="不支持读取该配置字段")
    return {"value": value}

@router.post("/system_config")
def update_system_config(payload: SystemConfigPayload):
    ConnectionRepository(config_path).update_legacy(
        api_key=payload.apiKey,
        base_url=payload.apiBaseUrl,
        model=payload.model,
        image_api_url=payload.imageApiUrl,
        memory_api_key=payload.memoryApiKey,
        memory_base_url=payload.memoryApiBaseUrl,
        memory_model=payload.memoryModel,
        memory_context_limit=payload.memoryContextLimit,
        preference_api_key=payload.preferenceApiKey,
        preference_base_url=payload.preferenceApiBaseUrl,
        preference_model=payload.preferenceModel,
    )
    reload_system_config_runtime()
    return {"status": "success"}


@router.post("/system_config/test")
def test_system_config():
    repository = ConnectionRepository(config_path)
    snapshot = repository.ensure_migrated()
    resolved = repository.resolve(snapshot, "story")
    config_data = resolved.ai_config() if resolved else {}
    missing = [
        label for key, label in (
            ("api_key", "API Key"),
            ("base_url", "API Base URL"),
            ("model", "模型名称"),
        )
        if not str(config_data.get(key) or "").strip()
    ]
    if missing:
        raise HTTPException(status_code=400, detail=f"请先填写并保存：{'、'.join(missing)}")
    engine = AIEngine(config_data)
    content, error = engine.chat_text(
        "你是 API 连通性测试助手。",
        "只回复“连接成功”四个字。",
        temp=0,
        trace_label="API连通性测试",
    )
    if error:
        raise HTTPException(status_code=502, detail=_connection_error_message(error))
    return {
        "connected": True,
        "message": "模型连接正常",
        "model": config_data.get("model", ""),
        "response": content.strip()[:50],
    }
