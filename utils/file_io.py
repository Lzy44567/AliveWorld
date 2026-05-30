# utils/file_io.py
# 100% 完整物理读写底稿 (请直接覆盖原文件)

import os
import json
import yaml
import glob
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, 'data')
CHAR_DIR = os.path.join(DATA_DIR, 'characters')
STYLE_DIR = os.path.join(DATA_DIR, 'styles')
SAVE_DIR = os.path.join(DATA_DIR, 'saves')
WORLD_DIR = os.path.join(DATA_DIR, 'worldbooks')
ENTITY_DIR = os.path.join(DATA_DIR, 'entities')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')

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

def init_save_folder(save_name: str):
    """
    🚀 V2.2 核心重构：只负责初始化空沙盒，不强制注入任何设定卡。
    """
    safe_fn = "".join(x for x in save_name if x.isalnum() or x in " _-")
    save_dir_path = os.path.join(SAVE_DIR, f"Save_{safe_fn}")
    
    local_world_dir = os.path.join(save_dir_path, 'worldbooks')
    local_style_dir = os.path.join(save_dir_path, 'styles')
    local_char_dir = os.path.join(save_dir_path, 'characters')
    local_entity_dir = os.path.join(save_dir_path, 'entities')
    
    for d in [save_dir_path, local_world_dir, local_style_dir, local_char_dir, local_entity_dir]:
        os.makedirs(d, exist_ok=True)
            
    return save_dir_path

def get_all_saves():
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
                        data['_filepath'] = state_file
                        data['_save_dir'] = folder_path
                        saves[data.get('save_name', folder_name)] = data
                except: 
                    pass
    return saves

def save_game_data(save_dir_path, data_dict):
    filepath = os.path.join(save_dir_path, "session_state.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=2)