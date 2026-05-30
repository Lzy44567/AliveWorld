# api/v1/lobby_routes.py
from fastapi import APIRouter, HTTPException
import os, glob, yaml
from utils.file_io import DATA_DIR, CHAR_DIR, STYLE_DIR, WORLD_DIR, SAVE_DIR, get_all_saves
from utils.sys_logger import read_logs_parsed

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

# ================= 新增：系统日志接口 =================
@router.get("/logs")
async def get_system_logs():
    """读取后端解析后的实时终端日志"""
    try:
        logs = read_logs_parsed()
        return {"logs": logs}
    except Exception as e:
        return {"logs": [{"time": "", "icon": "❌", "module": "API", "message": f"读取日志失败: {str(e)}"}]}

# ================= 新增：删除存档接口 =================
@router.delete("/saves/{save_name}")
async def delete_save(save_name: str):
    """根据名字查找并物理删除存档文件"""
    saves = get_all_saves()
    if save_name not in saves:
        raise HTTPException(status_code=404, detail="存档不存在")
        
    filepath = saves[save_name].get('_filepath')
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
            return {"status": "success", "message": f"存档 {save_name} 已彻底粉碎"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")
    
    raise HTTPException(status_code=404, detail="找不到存档物理文件")