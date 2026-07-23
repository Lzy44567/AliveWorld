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
from core.prompts import PROMPT_FILE, load_system_prompts
from core.worldbook import normalize_worldbook, save_worldbook_atomic
from core.asset_lifecycle import AssetLifecycleError, clone_yaml_asset, normalize_asset_name, rename_yaml_asset
from core.save_lifecycle import clone_save, rename_save
from core.session_manager import active_sessions
from core.entity_repository import EntityRepository
from core.image_generation.models import TERMINAL_STATUSES
from core.image_generation.repository import ImageTaskRepository
from core.worldbook_workshop_registry import retarget_workshops
from core.asset_workshop_registry import retarget_asset_workshops

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

@router.get("/assets")
async def get_lobby_assets():
    asset_meta = {asset_type: list_asset_summaries(asset_type) for asset_type in DIR_MAP}
    return {
        "worldbooks": [item["name"] for item in asset_meta["worldbooks"]],
        "styles": [item["name"] for item in asset_meta["styles"]],
        "characters": [item["name"] for item in asset_meta["characters"]],
        "entities": [item["name"] for item in asset_meta["entities"]],
        "asset_meta": asset_meta,
        "saves": list(get_all_saves().keys())
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
            if existing_path and asset_type != "worldbooks":
                existing_data = yaml.safe_load(existing_path.read_text(encoding='utf-8')) or {}
                if isinstance(existing_data, dict): parsed_data = {**existing_data, **parsed_data}
            if asset_type == "worldbooks":
                save_worldbook_atomic(file_path, parsed_data)
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    yaml.safe_dump(parsed_data, f, allow_unicode=True, sort_keys=False)
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
    try:
        new_name = normalize_asset_name(payload.new_name)
        target = clone_save(saves[save_name]["_save_dir"], new_name)
        return {"status": "success", "name": new_name, "path": str(target)}
    except AssetLifecycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.post("/saves/{save_name}/rename")
async def rename_save_route(save_name: str, payload: AssetLifecyclePayload):
    saves = get_all_saves()
    if save_name not in saves:
        raise HTTPException(status_code=404, detail="存档不存在")
    source_dir = saves[save_name]["_save_dir"]
    # Renaming while an image task is running would invalidate the runner's paths.
    for game in active_sessions.values():
        if Path(game.save_dir_path).resolve() == Path(source_dir).resolve():
            if any(task.status not in TERMINAL_STATUSES for task in ImageTaskRepository(source_dir).list()):
                raise HTTPException(status_code=409, detail="当前存档仍有生图任务运行，请完成或取消后重命名")
    try:
        new_name = normalize_asset_name(payload.new_name)
        target = rename_save(source_dir, new_name)
        retarget_workshops(source_dir, target, recursive=True)
        retarget_asset_workshops(source_dir, target, recursive=True)
        for game in active_sessions.values():
            if Path(game.save_dir_path).resolve() == Path(source_dir).resolve():
                game.save_name = new_name
                game.save_dir_path = str(target)
                game.entity_repository = EntityRepository(target)
        return {"status": "success", "name": new_name, "path": str(target)}
    except AssetLifecycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.get("/logs")
async def get_system_logs():
    try: return {"logs": read_logs_parsed()}
    except Exception as e: return {"logs": []}

@router.delete("/saves/{save_name}")
async def delete_save(save_name: str):
    saves = get_all_saves()
    if save_name not in saves: raise HTTPException(status_code=404, detail="不存在")
    save_dir = saves[save_name].get('_save_dir')
    if save_dir and os.path.exists(save_dir) and os.path.isdir(save_dir):
        try:
            shutil.rmtree(save_dir)  # 🚀 物理递归毁灭本存档子文件夹，绝不残留
            return {"status": "success"}
        except Exception as e: 
            raise HTTPException(status_code=500, detail="粉碎目录失败")
    raise HTTPException(status_code=404)

# ============ 🚀 问题 5 新增：提示词配置端点 ============
@router.get("/prompts")
async def get_all_prompts():
    try: return load_system_prompts()
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.post("/prompts")
async def save_all_prompts(payload: SavePromptsPayload):
    try:
        with open(PROMPT_FILE, 'w', encoding='utf-8') as f:
            yaml.safe_dump(payload.prompts, f, allow_unicode=True, sort_keys=False)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存提示词失败: {str(e)}")
