# utils/file_io.py
import os, json, yaml, glob
from datetime import datetime

# 找到项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 统一指向你新建的 data 文件夹
DATA_DIR = os.path.join(BASE_DIR, 'data')
CHAR_DIR = os.path.join(DATA_DIR, 'characters')
STYLE_DIR = os.path.join(DATA_DIR, 'styles')
SAVE_DIR = os.path.join(DATA_DIR, 'saves')
WORLD_DIR = os.path.join(DATA_DIR, 'worldbooks')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')

# 确保文件夹存在
for d in [CHAR_DIR, STYLE_DIR, SAVE_DIR, WORLD_DIR]: 
    os.makedirs(d, exist_ok=True)

def load_settings():
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {"default_style": "默认 (无)"}

def save_settings(data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False)

def load_yaml_files(directory):
    data_dict = {}
    for f in glob.glob(os.path.join(directory, "*.yml")):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and 'name' in data: 
                    data['_filepath'] = f
                    data_dict[data['name']] = data
        except: pass
    return data_dict

def get_all_saves():
    saves = {}
    for f in glob.glob(os.path.join(SAVE_DIR, "*.json")):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                data['_filepath'] = f
                saves[data.get('save_name', '未命名')] = data
        except: pass
    return saves

def save_game_data(save_name, data_dict):
    safe_fn = "".join(x for x in save_name if x.isalnum() or x in " _-")
    filepath = os.path.join(SAVE_DIR, f"AutoSave_{safe_fn}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=2)