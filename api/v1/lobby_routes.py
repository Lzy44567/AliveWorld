# api/v1/lobby_routes.py
# 100% 完整物理读写底稿 (请直接覆盖原文件)

import os
import yaml
import shutil
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from utils.file_io import DATA_DIR, CHAR_DIR, STYLE_DIR, WORLD_DIR, ENTITY_DIR, SAVE_DIR, get_all_saves
from utils.asset_catalog import list_asset_names, list_asset_summaries, personal_asset_dir, resolve_asset_path, resolve_template_path
from utils.sys_logger import read_logs_parsed
from core.worldbook import normalize_worldbook, save_worldbook_atomic
from core.character_profiles import coordinate_character_write
from utils.atomic_yaml import save_yaml_atomic
from core.asset_lifecycle import AssetLifecycleError, clone_yaml_asset, normalize_asset_name, rename_yaml_asset
from core.save_lifecycle import clone_save, rename_save
from core.session_manager import (
    MutationBusyError, active_sessions, mutation_guard, retarget_session,
    save_identity, unregister_session,
)
from core.entity_repository import EntityRepository
from core.image_generation.models import TERMINAL_STATUSES
from core.image_generation.repository import ImageTaskRepository
from core.worldbook_workshop_registry import retarget_workshops
from core.asset_workshop_registry import retarget_asset_workshops
from utils.legacy_migration import discover_legacy_root, has_personal_data, migrate_legacy_data
from utils.runtime_paths import PATHS

router = APIRouter()

DIR_MAP = {
    "worldbooks": WORLD_DIR, 
    "styles": STYLE_DIR, 
    "characters": CHAR_DIR, 
    "entities": ENTITY_DIR
}

class AssetPayload(BaseModel):
    content: Optional[str] = None
    parsed_data: Optional[Dict[str, Any]] = None
    overwrite: bool = False

class SavePromptsPayload(BaseModel):
    prompts: Dict[str, str]

class AssetLifecyclePayload(BaseModel):
    new_name: str

class LegacyMigrationPayload(BaseModel):
    source_root: Optional[str] = None
    overwrite_config: bool = False

@router.get("/assets")
async def get_lobby_assets():
    # Official/package templates are managed by the world-package catalog. They
    # remain available to authoring, but must not impersonate personal assets.
    asset_meta = {asset_type: list_asset_summaries(asset_type, include_templates=False) for asset_type in DIR_MAP}
    return {
        "worldbooks": [item["name"] for item in asset_meta["worldbooks"]],
        "styles": [item["name"] for item in asset_meta["styles"]],
        "characters": [item["name"] for item in asset_meta["characters"]],
        "entities": [item["name"] for item in asset_meta["entities"]],
        "asset_meta": asset_meta,
        "saves": list(get_all_saves().keys())
    }

@router.post("/migration/legacy")
async def import_legacy_data(payload: LegacyMigrationPayload):
    source = (
        Path(payload.source_root).expanduser().resolve()
        if str(payload.source_root or "").strip()
        else discover_legacy_root()
    )
    if source is None:
        raise HTTPException(
            status_code=404,
            detail="未自动发现旧版 AliveWorld；可展开高级选项并填写旧项目根目录。",
        )
    if source in {PATHS.user_root.resolve(), PATHS.resource_root.resolve()}:
        raise HTTPException(status_code=400, detail="所选目录是当前数据目录，无需重复同步")
    if not (source / "data").is_dir():
        raise HTTPException(status_code=400, detail="所选目录中没有 data 文件夹")
    if not has_personal_data(source) and not (source / "config.yml").is_file():
        raise HTTPException(status_code=400, detail="所选目录中没有可同步的个人资产或配置")
    try:
        report = migrate_legacy_data(
            source,
            overwrite_config=payload.overwrite_config,
        )
        if report.copied_config:
            # Importing configuration from Settings must become effective now,
            # rather than waiting for the next application restart.
            from api.v1.game_routes import reload_system_config_runtime
            reload_system_config_runtime()
        return {
            "status": "success",
            "source_root": report.source_root,
            "copied_files": report.copied_files,
            "skipped_conflicts": report.skipped_conflicts,
            "copied_config": report.copied_config,
        }
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"同步旧资产失败：{exc}") from exc

@router.get("/migration/legacy/status")
async def legacy_migration_status():
    marker = PATHS.user_root / "legacy_migration.json"
    if marker.is_file():
        return {"should_prompt": False, "completed": True, "source_root": None}
    source = discover_legacy_root()
    return {
        "should_prompt": source is not None,
        "completed": False,
        "source_root": str(source) if source else None,
    }

@router.post("/assets/{asset_type}/{asset_name}")
async def save_asset(asset_type: str, asset_name: str, payload: AssetPayload):
    if asset_type not in DIR_MAP: raise HTTPException(status_code=400, detail="未知的资产类型")
    existing_path = resolve_asset_path(asset_type, asset_name)
    if existing_path and not payload.overwrite:
        raise HTTPException(status_code=409, detail=f"已存在同名资产“{asset_name}”，需要明确确认覆盖")
    if existing_path and resolve_template_path(asset_type, asset_name) == existing_path:
        raise HTTPException(status_code=403, detail="模板资产不能被覆盖，请另存为个人资产")
    file_path = str(existing_path) if existing_path else os.path.join(DIR_MAP[asset_type], f"{asset_name}.yml")
    try:
        if payload.parsed_data:
            parsed_data = normalize_worldbook(payload.parsed_data) if asset_type == "worldbooks" else payload.parsed_data
            if existing_path and asset_type == "worldbooks":
                existing_data = yaml.safe_load(existing_path.read_text(encoding='utf-8')) or {}
                if isinstance(existing_data, dict) and existing_data.get("_external_import"):
                    parsed_data["_external_import"] = existing_data["_external_import"]
            if existing_path and asset_type != "worldbooks":
                existing_data = yaml.safe_load(existing_path.read_text(encoding='utf-8')) or {}
                if isinstance(existing_data, dict): parsed_data = {**existing_data, **parsed_data}
            if asset_type == 'characters':
                parsed_data = coordinate_character_write(existing_data if existing_path else {}, payload.parsed_data)
            if asset_type == "worldbooks":
                save_worldbook_atomic(file_path, parsed_data)
            elif asset_type == 'characters':
                save_yaml_atomic(file_path, parsed_data)
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    yaml.safe_dump(parsed_data, f, allow_unicode=True, sort_keys=False)
        else:
            if asset_type == 'characters':
                incoming = yaml.safe_load(payload.content)
                if not isinstance(incoming, dict):
                    raise ValueError('角色卡内容必须是对象')
                existing = yaml.safe_load(existing_path.read_text(encoding='utf-8')) if existing_path else {}
                result = coordinate_character_write(existing, incoming)
                save_yaml_atomic(file_path, result)
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(payload.content)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")

@router.get("/assets/{asset_type}/{asset_name}")
async def get_asset_detail(asset_type: str, asset_name: str):
    if asset_type not in DIR_MAP: raise HTTPException(status_code=400, detail="未知的资产类型")
    path = resolve_asset_path(asset_type, asset_name)
    if path:
        try:
            content = path.read_text(encoding='utf-8')
            return {"content": content, "parsed": yaml.safe_load(content) or {}}
        except (OSError, yaml.YAMLError):
            raise HTTPException(status_code=500, detail="资产文件读取失败")
    raise HTTPException(status_code=404, detail="找不到该资产文件")

@router.delete("/assets/{asset_type}/{asset_name}")
async def delete_asset(asset_type: str, asset_name: str):
    if asset_type not in DIR_MAP: raise HTTPException(status_code=400, detail="未知类型")
    
    personal_path = os.path.join(DIR_MAP[asset_type], f"{asset_name}.yml")
    if os.path.exists(personal_path):
        try:
            os.remove(personal_path)
            return {"status": "success"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"文件删除失败: {e}")

    personal_dir = personal_asset_dir(asset_type)
    if personal_dir:
        for path in personal_dir.glob("*.yml"):
            try:
                data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
                if isinstance(data, dict) and data.get('name') == asset_name:
                    path.unlink()
                    return {"status": "success"}
            except (OSError, yaml.YAMLError):
                continue

    if resolve_template_path(asset_type, asset_name):
        raise HTTPException(status_code=403, detail="受控模板不能从个人资产库删除")
    raise HTTPException(status_code=404, detail="无法删除")

@router.post("/assets/{asset_type}/{asset_name}/clone")
async def clone_asset(asset_type: str, asset_name: str, payload: AssetLifecyclePayload):
    if asset_type not in DIR_MAP:
        raise HTTPException(status_code=400, detail="未知的资产类型")
    try:
        new_name = normalize_asset_name(payload.new_name)
        if resolve_asset_path(asset_type, new_name):
            raise AssetLifecycleError(f"已存在同名资产“{new_name}”")
        source = resolve_asset_path(asset_type, asset_name)
        target = clone_yaml_asset(DIR_MAP[asset_type], asset_name, new_name, worldbook=asset_type == "worldbooks", source_path=source)
        return {"status": "success", "name": new_name, "path": str(target)}
    except AssetLifecycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.post("/assets/{asset_type}/{asset_name}/rename")
async def rename_asset(asset_type: str, asset_name: str, payload: AssetLifecyclePayload):
    if asset_type not in DIR_MAP:
        raise HTTPException(status_code=400, detail="未知的资产类型")
    try:
        new_name = normalize_asset_name(payload.new_name)
        conflict = resolve_asset_path(asset_type, new_name)
        source = resolve_asset_path(asset_type, asset_name)
        if conflict and source and conflict.resolve() != source.resolve():
            raise AssetLifecycleError(f"已存在同名资产“{new_name}”")
        target = rename_yaml_asset(DIR_MAP[asset_type], asset_name, new_name, worldbook=asset_type == "worldbooks")
        if asset_type == "worldbooks" and source:
            retarget_workshops(source, target)
        elif source:
            retarget_asset_workshops(source, target)
        return {"status": "success", "name": new_name, "path": str(target)}
    except AssetLifecycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.post("/saves/{save_name}/clone")
async def clone_save_route(save_name: str, payload: AssetLifecyclePayload):
    saves = get_all_saves()
    if save_name not in saves:
        raise HTTPException(status_code=404, detail="存档不存在")
    source_dir = saves[save_name]["_save_dir"]
    try:
        with mutation_guard("story", save_identity(source_dir)):
            new_name = normalize_asset_name(payload.new_name)
            target = clone_save(source_dir, new_name)
            return {"status": "success", "name": new_name, "path": str(target)}
    except MutationBusyError as exc:
        raise HTTPException(status_code=409, detail="故事仍在推演，完成后才能克隆") from exc
    except AssetLifecycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.post("/saves/{save_name}/rename")
async def rename_save_route(save_name: str, payload: AssetLifecyclePayload):
    saves = get_all_saves()
    if save_name not in saves:
        raise HTTPException(status_code=404, detail="存档不存在")
    source_dir = saves[save_name]["_save_dir"]
    try:
        with mutation_guard("story", save_identity(source_dir)):
            matching = [
                (session_id, game) for session_id, game in active_sessions.items()
                if Path(game.save_dir_path).resolve() == Path(source_dir).resolve()
            ]
            if matching and any(task.status not in TERMINAL_STATUSES for task in ImageTaskRepository(source_dir).list()):
                raise HTTPException(status_code=409, detail="当前存档仍有生图任务运行，请完成或取消后重命名")
            new_name = normalize_asset_name(payload.new_name)
            target = rename_save(source_dir, new_name)
            retarget_workshops(source_dir, target, recursive=True)
            retarget_asset_workshops(source_dir, target, recursive=True)
            for session_id, game in matching:
                game.save_name = new_name
                game.save_dir_path = str(target)
                game.entity_repository = EntityRepository(target)
                retarget_session(session_id, source_dir, str(target))
            return {"status": "success", "name": new_name, "path": str(target)}
    except MutationBusyError as exc:
        raise HTTPException(status_code=409, detail="故事仍在推演，完成后才能重命名") from exc
    except AssetLifecycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.get("/logs")
async def get_system_logs(category: str = "", trace_id: str = "", limit: int = 500):
    try: return {"logs": read_logs_parsed(category=category, trace_id=trace_id, limit=limit)}
    except Exception as e: return {"logs": []}

@router.delete("/saves/{save_name}")
async def delete_save(save_name: str):
    saves = get_all_saves()
    if save_name not in saves: raise HTTPException(status_code=404, detail="不存在")
    save_dir = saves[save_name].get('_save_dir')
    if save_dir and os.path.exists(save_dir) and os.path.isdir(save_dir):
        try:
            with mutation_guard("story", save_identity(save_dir)):
                matching_ids = [
                    session_id for session_id, game in active_sessions.items()
                    if Path(game.save_dir_path).resolve() == Path(save_dir).resolve()
                ]
                shutil.rmtree(save_dir)
                for session_id in matching_ids:
                    unregister_session(session_id)
                return {"status": "success"}
        except MutationBusyError as exc:
            raise HTTPException(status_code=409, detail="故事仍在推演，完成后才能删除") from exc
        except Exception as e: 
            raise HTTPException(status_code=500, detail="粉碎目录失败")
    raise HTTPException(status_code=404)

# 旧接口故意保留为明确的 410，避免旧客户端继续无鉴权覆盖发行基线。
@router.get("/prompts")
async def get_all_prompts():
    raise HTTPException(status_code=410, detail="旧提示词接口已停用；请使用受保护的提示词工作台")

@router.post("/prompts")
async def save_all_prompts(payload: SavePromptsPayload):
    raise HTTPException(status_code=410, detail="旧提示词接口已停用；请使用受保护的提示词工作台")
