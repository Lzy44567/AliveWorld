# utils/file_io.py
# 100% 完整物理读写底稿 (请直接覆盖原文件)

import os
import json
import yaml
import glob
import shutil
from datetime import datetime

# 找到项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 统一指向项目底层的 data 文件夹
DATA_DIR = os.path.join(BASE_DIR, 'data')
CHAR_DIR = os.path.join(DATA_DIR, 'characters')
STYLE_DIR = os.path.join(DATA_DIR, 'styles')
SAVE_DIR = os.path.join(DATA_DIR, 'saves')
WORLD_DIR = os.path.join(DATA_DIR, 'worldbooks')
ENTITY_DIR = os.path.join(DATA_DIR, 'entities')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')

# 确保所有全局预设资产文件夹及存档主目录健康存在
for d in [CHAR_DIR, STYLE_DIR, SAVE_DIR, WORLD_DIR, ENTITY_DIR]: 
    os.makedirs(d, exist_ok=True)

def load_settings():
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f: 
            return json.load(f)
    except: 
        return {"default_style": "默认 (无)"}

def save_settings(data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f: 
        json.dump(data, f, ensure_ascii=False)

def load_yaml_files(directory):
    data_dict = {}
    for f in glob.glob(os.path.join(directory, "*.yml")):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and 'name' in data: 
                    data['_filepath'] = f
                    data_dict[data['name']] = data
        except: 
            pass
    return data_dict

def init_save_folder(save_name: str, global_worldbook: str = None, global_style: str = None, global_char: str = None):
    """
    🚀 核心改动：初始化一个全新故事的沙盒文件夹，将选定的全局模板复制为局内专属初始资产
    """
    # 过滤可能导致路径报错的特殊字符
    safe_fn = "".join(x for x in save_name if x.isalnum() or x in " _-")
    save_dir_path = os.path.join(SAVE_DIR, f"Save_{safe_fn}")
    
    local_world_dir = os.path.join(save_dir_path, 'worldbooks')
    local_style_dir = os.path.join(save_dir_path, 'styles')
    local_char_dir = os.path.join(save_dir_path, 'characters')
    local_entity_dir = os.path.join(save_dir_path, 'entities')
    
    # 初始化本存档的子沙盒结构
    for d in [save_dir_path, local_world_dir, local_style_dir, local_char_dir, local_entity_dir]:
        os.makedirs(d, exist_ok=True)
        
    # 拷贝局部世界书 (从全局拷贝到局部沙盒)
    if global_worldbook and global_worldbook not in ["无界域 (暂不加载)", ""]:
        for f in glob.glob(os.path.join(WORLD_DIR, "*.yml")):
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    data = yaml.safe_load(file)
                    if data and data.get('name') == global_worldbook:
                        shutil.copy2(f, os.path.join(local_world_dir, os.path.basename(f)))
                        break
            except: 
                pass
            
    # 拷贝局部文风卡
    if global_style and global_style not in ["默认 (无)", ""]:
        for f in glob.glob(os.path.join(STYLE_DIR, "*.yml")):
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    data = yaml.safe_load(file)
                    if data and data.get('name') == global_style:
                        shutil.copy2(f, os.path.join(local_style_dir, os.path.basename(f)))
                        break
            except: 
                pass
            
    # 拷贝选中的局部角色卡 (问题 3 的基石)
    if global_char and global_char not in ["空白模板 (无名者)", "冒险者", ""]:
        for f in glob.glob(os.path.join(CHAR_DIR, "*.yml")):
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    data = yaml.safe_load(file)
                    if data and data.get('name') == global_char:
                        shutil.copy2(f, os.path.join(local_char_dir, os.path.basename(f)))
                        break
            except: 
                pass
            
    return save_dir_path

def get_all_saves():
    """
    🚀 核心改动：扫描存档文件夹沙盒，读取其下的 session_state.json 描述文件
    """
    saves = {}
    if not os.path.exists(SAVE_DIR): 
        return saves
        
    for folder_name in os.listdir(SAVE_DIR):
        folder_path = os.path.join(SAVE_DIR, folder_name)
        if os.path.isdir(folder_path):
            state_file = os.path.join(folder_path, "session_state.json")
            if os.path.exists(state_file):
                try:
                    with open(state_file, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        # 保存相关的持久化上下文定位标记
                        data['_filepath'] = state_file
                        data['_save_dir'] = folder_path
                        saves[data.get('save_name', folder_name)] = data
                except: 
                    pass
    return saves

def save_game_data(save_dir_path, data_dict):
    """
    🚀 核心改动：不再将存档平铺到 data/saves 下，而是写入该存档沙盒专属的 session_state.json 中
    """
    filepath = os.path.join(save_dir_path, "session_state.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=2)