# api/v1/lobby_routes.py
from fastapi import APIRouter
import os, glob, yaml
from utils.file_io import DATA_DIR, CHAR_DIR, STYLE_DIR, WORLD_DIR, get_all_saves

router = APIRouter()

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
    # 顺便把 saves 文件夹里的存档名字也扫出来发给前端
    return {
        "worldbooks": get_yaml_names(WORLD_DIR),
        "styles": get_yaml_names(STYLE_DIR),
        "characters": get_yaml_names(CHAR_DIR),
        "saves": list(get_all_saves().keys()) # 获取所有存档名称
    }