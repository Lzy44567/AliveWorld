# api/v1/lobby_routes.py
# 100% 完整物理读写底稿 (请直接覆盖原文件)

import os
import glob
import yaml
import shutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from utils.file_io import DATA_DIR, CHAR_DIR, STYLE_DIR, WORLD_DIR, ENTITY_DIR, SAVE_DIR, get_all_saves
from utils.sys_logger import read_logs_parsed
from core.prompts import PROMPT_FILE, load_system_prompts

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

class SavePromptsPayload(BaseModel):
    prompts: Dict[str, str]

def get_yaml_names(directory):
    names = []
    if not os.path.exists(directory): return names
    for f in glob.glob(os.path.join(directory, "*.yml")):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and 'name' in data: names.append(data['name'])
        except: pass
    return names

@router.get("/assets")
async def get_lobby_assets():
    return {
        "worldbooks": get_yaml_names(WORLD_DIR),
        "styles": get_yaml_names(STYLE_DIR),
        "characters": get_yaml_names(CHAR_DIR),
        "entities": get_yaml_names(ENTITY_DIR),  # 🚀 返回实体库
        "saves": list(get_all_saves().keys())
    }

@router.post("/assets/{asset_type}/{asset_name}")
async def save_asset(asset_type: str, asset_name: str, payload: AssetPayload):
    if asset_type not in DIR_MAP: raise HTTPException(status_code=400, detail="未知的资产类型")
    file_path = os.path.join(DIR_MAP[asset_type], f"{asset_name}.yml")
    try:
        if payload.parsed_data:
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(payload.parsed_data, f, allow_unicode=True, sort_keys=False)
        else:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(payload.content)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")

@router.get("/assets/{asset_type}/{asset_name}")
async def get_asset_detail(asset_type: str, asset_name: str):
    if asset_type not in DIR_MAP: raise HTTPException(status_code=400, detail="未知的资产类型")
    for f in glob.glob(os.path.join(DIR_MAP[asset_type], "*.yml")):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and data.get('name') == asset_name:
                    file.seek(0)
                    return {"content": file.read(), "parsed": data}
        except: pass
    raise HTTPException(status_code=404, detail="找不到该资产文件")

@router.delete("/assets/{asset_type}/{asset_name}")
async def delete_asset(asset_type: str, asset_name: str):
    if asset_type not in DIR_MAP: raise HTTPException(status_code=400, detail="未知类型")
    
    file_path = os.path.join(DIR_MAP[asset_type], f"{asset_name}.yml")
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return {"status": "success"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"文件删除失败: {e}")
            
    for f in glob.glob(os.path.join(DIR_MAP[asset_type], "*.yml")):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and data.get('name') == asset_name:
                    os.remove(f)
                    return {"status": "success"}
        except: pass
    raise HTTPException(status_code=404, detail="无法删除")

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