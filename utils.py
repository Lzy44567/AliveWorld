# utils.py
import os, json, yaml, glob, copy
from datetime import datetime
import streamlit as st
from sys_logger import get_logger

log = get_logger()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR, CHAR_DIR, STYLE_DIR, SAVE_DIR, WORLD_DIR = [os.path.join(BASE_DIR, d) for d in ['logs', 'characters', 'styles', 'saves', 'worldbooks']]
for d in [LOG_DIR, CHAR_DIR, STYLE_DIR, SAVE_DIR, WORLD_DIR]: os.makedirs(d, exist_ok=True)
SETTINGS_FILE = os.path.join(BASE_DIR, 'settings.json')

def load_settings():
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {"default_style": "默认 (无)"}

def save_settings(data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False)

def auto_save_game():
    if not st.session_state.get('session_id'): return
    save_data = {
        "save_name": st.session_state.session_save_name, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "char_info": st.session_state.char_info, "style_info": st.session_state.style_info, "world_info_base": st.session_state.world_info_base,
        "world_entries": st.session_state.world_entries, "player_state": st.session_state.player_state, "dynamic_bars": st.session_state.dynamic_bars,
        "active_buffs": st.session_state.active_buffs, "player_properties": st.session_state.player_properties,
        "npc_states": getattr(st.session_state, 'npc_states', {}),
        "last_deltas": st.session_state.last_deltas, "chat_messages": st.session_state.chat_messages,
        "context_history": st.session_state.context_history, "state_snapshots": st.session_state.state_snapshots
    }
    safe_fn = "".join(x for x in st.session_state.session_save_name if x.isalnum() or x in " _-")
    with open(os.path.join(SAVE_DIR, f"AutoSave_{safe_fn}.json"), 'w', encoding='utf-8') as f: json.dump(save_data, f, ensure_ascii=False, indent=2)

def take_snapshot():
    snap = {
        "player_state": copy.deepcopy(st.session_state.player_state), "dynamic_bars": copy.deepcopy(st.session_state.dynamic_bars),
        "active_buffs": copy.deepcopy(st.session_state.active_buffs), "player_properties": copy.deepcopy(st.session_state.player_properties),
        "npc_states": copy.deepcopy(getattr(st.session_state, 'npc_states', {})),
        "last_deltas": copy.deepcopy(st.session_state.last_deltas), "chat_messages": copy.deepcopy(st.session_state.chat_messages),
        "context_history": copy.deepcopy(st.session_state.context_history)
    }
    st.session_state.state_snapshots.append(snap)
    if len(st.session_state.state_snapshots) > 20: st.session_state.state_snapshots.pop(0)

def load_yaml_files(directory):
    data_dict = {}
    for f in glob.glob(os.path.join(directory, "*.yml")):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and 'name' in data: data['_filepath'] = f; data_dict[data['name']] = data
        except: pass
    return data_dict

def build_active_world_info(current_context, player_action):
    active_lore = st.session_state.world_info_base + "\n"
    search_text = current_context + "\n" + player_action
    triggered_entries = []
    for entry in st.session_state.world_entries:
        keys_str = entry.get('keys', '')
        if not keys_str: continue
        keywords = [kw.strip() for kw in keys_str.split(',') if kw.strip()]
        if not keywords: continue
        if any(kw in search_text for kw in keywords):
            active_lore += f"【设定 - {entry.get('name', '补充')}】：{entry.get('content', '')}\n"
            triggered_entries.append(entry.get('name'))
    return active_lore, triggered_entries

def apply_state_updates(result):
    ps, deltas = st.session_state.player_state, st.session_state.last_deltas
    
    nums = result.get('numeric_changes', {}) if isinstance(result.get('numeric_changes'), dict) else {}
    for k in ['hp', 'max_hp', 'mana', 'max_mana']: deltas[k] = nums.get(k, 0)
    
    new_buffs = result.get('new_buffs', {}) if isinstance(result.get('new_buffs'), dict) else {}
    remove_buffs = result.get('remove_buffs', []) if isinstance(result.get('remove_buffs'), list) else ([result.get('remove_buffs')] if isinstance(result.get('remove_buffs'), str) else [])
    for bn, bd in new_buffs.items(): 
        if isinstance(bd, dict): st.session_state.active_buffs[bn] = bd
    for bn in remove_buffs: st.session_state.active_buffs.pop(bn, None)
    
    to_remove = []
    for bn, bd in st.session_state.active_buffs.items():
        deltas['hp'] += bd.get('hp_per_turn', 0); deltas['mana'] += bd.get('mana_per_turn', 0)
        if bd.get('duration', -1) != -1:
            bd['duration'] -= 1
            if bd['duration'] <= 0: to_remove.append(bn)
    for b in to_remove: del st.session_state.active_buffs[b]
    
    ps['max_hp'] += deltas['max_hp']; ps['max_mana'] += deltas['max_mana']
    ps['hp'] = max(0, min(ps['hp'] + deltas['hp'], ps['max_hp'])); ps['mana'] = max(0, min(ps['mana'] + deltas['mana'], ps['max_mana']))
    
    bars_update = result.get('dynamic_bars', {}) if isinstance(result.get('dynamic_bars'), dict) else {}
    for bn, bd in bars_update.items():
        if not isinstance(bd, dict): continue
        if bn not in st.session_state.dynamic_bars: 
            # 修复：AI新增状态条时，精确读取 current，如果没有则给 0，防止刚建出来就被删！
            init_val = bd.get('current', 0)
            st.session_state.dynamic_bars[bn] = {"current": init_val, "max": bd.get('max', 100)}
        else:
            # 修复：已有状态条只加 change
            st.session_state.dynamic_bars[bn]["current"] = min(st.session_state.dynamic_bars[bn]["current"] + bd.get('change', 0), st.session_state.dynamic_bars[bn]["max"])
        
        # 删除归零的条
        if st.session_state.dynamic_bars[bn]["current"] <= 0: del st.session_state.dynamic_bars[bn]
            
    npc_up = result.get('npc_states', {}) if isinstance(result.get('npc_states'), dict) else {}
    for k, v in npc_up.items():
        if isinstance(v, dict) or isinstance(v, list): v = str(v).replace("{", "").replace("}", "").replace("'", "")
        st.session_state.npc_states[k] = v

    props_up = result.get('status_updates', {}) if isinstance(result.get('status_updates'), dict) else {}
    props_del = result.get('status_deletions', []) if isinstance(result.get('status_deletions'), list) else ([result.get('status_deletions')] if isinstance(result.get('status_deletions'), str) else [])
    
    for k in props_del:
        st.session_state.player_properties.pop(k, None)
        st.session_state.dynamic_bars.pop(k, None)
        st.session_state.active_buffs.pop(k, None)
        st.session_state.npc_states.pop(k, None) 
        
    for k, v in props_up.items():
        if isinstance(v, dict) or isinstance(v, list): v = str(v).replace("{", "").replace("}", "").replace("'", "")
        st.session_state.player_properties[k] = v
            
    if ps['hp'] <= 0: st.session_state.game_over = True