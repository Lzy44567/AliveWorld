# core/game_session.py
# 100% 完整物理读写底稿 (请直接覆盖原文件)

import os
import copy
import yaml
import glob
from datetime import datetime
from core.undercurrent import UndercurrentEngine
from core.resolution_engine import DualTrackResolver

class GameSession:
    def __init__(self, ai_engine, save_name="", save_dir_path=""):
        self.ai_engine = ai_engine
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.save_name = save_name
        self.save_dir_path = save_dir_path
        self.is_game_over = False
        
        self.char_info = ""
        self.style_info = ""
        self.world_info_base = ""
        self.world_entries = []
        
        self.word_limit = 500
        self.description = ""  # 故事简述 / Plot Compass
        
        self.state = {
            "player": {"hp": 100, "max_hp": 100, "mana": 100, "max_mana": 100},
            "last_deltas": {"hp": 0, "max_hp": 0, "mana": 0, "max_mana": 0},
            "properties": {"身体": "完好"},
            "bars": {}, "buffs": {}, "npcs": {}
        }
        self.history = {"chat_messages": [], "context_history": []}
        self.snapshots = [] 
        
        self.undercurrent = UndercurrentEngine(self.ai_engine)
        self.resolver = DualTrackResolver()

    def start_new_game(self, description, opening):
        self.description = description
        self.history["chat_messages"] = [{"role": "ai", "content": opening}]
        self.history["context_history"] = [opening]

    def refresh_context_from_local(self):
        """
        🚀 核心：每次推演前，扫描并合并沙盒目录下所有激活的设定卡片！
        """
        if not self.save_dir_path or not os.path.exists(self.save_dir_path):
            return

        # 1. 组装文风
        styles = []
        for f in glob.glob(os.path.join(self.save_dir_path, 'styles', '*.yml')):
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and data.get('is_active', True):
                    styles.append(data.get('content', ''))
        self.style_info = "\n---\n".join(styles)

        # 2. 组装世界书
        worlds_base = []
        self.world_entries = []
        for f in glob.glob(os.path.join(self.save_dir_path, 'worldbooks', '*.yml')):
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and data.get('is_active', True):
                    if data.get('global_setting'):
                        worlds_base.append(f"[{data.get('name', '界域法则')}]：{data.get('global_setting')}")
                    self.world_entries.extend(data.get('entries', []))
        self.world_info_base = "\n".join(worlds_base)

        # 3. 🚀 组装角色 (区分玩家化身与出场 NPC)
        player_chars = []
        npc_chars = []
        for f in glob.glob(os.path.join(self.save_dir_path, 'characters', '*.yml')):
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and data.get('is_active', True):
                    desc = f"[{data.get('name', '未知实体')}]：{data.get('description', '')}"
                    if data.get('is_player', False):
                        player_chars.append(desc)
                    else:
                        npc_chars.append(desc)
        
        self.char_info = "\n---\n".join(player_chars) if player_chars else "无名冒险者"
        
        if npc_chars:
            self.world_info_base += "\n\n【当前登场的重要NPC与势力】：\n" + "\n".join(npc_chars)
        
        # 4. 🚀 注入 Plot Compass 故事主导向
        if self.description:
            self.world_info_base = f"【🔥宇宙主导向 (最高法则)】：{self.description}\n\n" + self.world_info_base

    def process_turn(self, user_action: str):
        self._take_snapshot()
        self.history["chat_messages"].append({"role": "user", "content": user_action})
        
        # 每次动作前刷新最新沙盒环境
        self.refresh_context_from_local()
        
        result = self.resolver.resolve(self, user_action)
        if not result or not result.get('settlement'): return {"error": True}
            
        settlement = result['settlement']
        self.history["chat_messages"].append({"role": "reactions", "content": result['reactions']})
        self.history["chat_messages"].append({"role": "system", "content": f"命运变数: {result['chosen_reaction']['description']}"})
        
        story_text = settlement.get('story_text', '').replace('\\n', '\n')
        self.history["chat_messages"].append({"role": "ai", "content": story_text})
        
        recent_context = self.get_context_text()
        undercurrent_events = self.undercurrent.tick(recent_context)
        
        if undercurrent_events:
            for ev in undercurrent_events:
                self.history["chat_messages"].append({"role": "system", "content": f"🌌 潜流涌动: {ev}"})
        
        self._apply_state_updates(settlement)
        self.history["context_history"].append(f"玩家：{user_action}\n结果：{story_text}")
        
        return result

    def get_context_text(self): 
        return "\n".join(self.history["context_history"][-3:])
        
    def get_dynamic_state_for_ai(self): 
        return {
            "stats": self.state['player'], "bars": self.state['bars'], 
            "properties": self.state['properties'], "buffs": self.state['buffs'], "npcs": self.state['npcs']
        }
        
    def build_active_world_info(self, action):
        active = self.world_info_base + "\n"
        search = self.get_context_text() + "\n" + action
        triggered_entries = []
        for ent in self.world_entries:
            keys = [k.strip() for k in ent.get('keys', '').split(',') if k.strip()]
            if any(k in search for k in keys): 
                active += f"【设定 - {ent.get('name')}】：{ent.get('content', '')}\n"
                triggered_entries.append(ent.get('name'))
        active += "\n【隐藏的暗流因果】：\n" + self.undercurrent.get_ledger_context()
        return active, triggered_entries

    def _apply_state_updates(self, result):
        ps, deltas = self.state['player'], self.state['last_deltas']
        nums = result.get('numeric_changes', {})
        for k in ['hp', 'max_hp', 'mana', 'max_mana']: deltas[k] = nums.get(k, 0)
        
        for bn, bd in result.get('new_buffs', {}).items():
            if isinstance(bd, dict): self.state['buffs'][bn] = bd
        for bn in (result.get('remove_buffs', []) if isinstance(result.get('remove_buffs'), list) else []): self.state['buffs'].pop(bn, None)
            
        to_remove = []
        for bn, bd in self.state['buffs'].items():
            deltas['hp'] += bd.get('hp_per_turn', 0); deltas['mana'] += bd.get('mana_per_turn', 0)
            if bd.get('duration', -1) != -1:
                bd['duration'] -= 1
                if bd['duration'] <= 0: to_remove.append(bn)
        for b in to_remove: del self.state['buffs'][b]
        
        ps['max_hp'] += deltas['max_hp']; ps['max_mana'] += deltas['max_mana']
        ps['hp'] = max(0, min(ps['hp'] + deltas['hp'], max(1, ps['max_hp'])))
        ps['mana'] = max(0, min(ps['mana'] + deltas['mana'], max(1, ps['max_mana'])))
        if ps['hp'] <= 0: self.is_game_over = True
        
        for bn, bd in result.get('dynamic_bars', {}).items():
            if not isinstance(bd, dict): continue
            if bn not in self.state['bars']: self.state['bars'][bn] = {"current": bd.get('current', 0), "max": bd.get('max', 100)}
            else: self.state['bars'][bn]["current"] = max(0, min(self.state['bars'][bn]["current"] + bd.get('change', 0), self.state['bars'][bn]["max"]))
                
        for k, v in result.get('npc_states', {}).items():
            if isinstance(v, dict): v = ", ".join([f"{dk}:{dv}" for dk, dv in v.items()])
            self.state['npcs'][k] = str(v)
            
        for k, v in result.get('status_updates', {}).items(): 
            if isinstance(v, dict): v = ", ".join([f"{dk}:{dv}" for dk, dv in v.items()])
            self.state['properties'][k] = str(v)
            
        dels = result.get('status_deletions', [])
        if not isinstance(dels, list): dels = []
        for k in dels:
            for group in ['properties', 'bars', 'buffs', 'npcs']: self.state[group].pop(k, None)

    def _take_snapshot(self):
        snap = {
            "state": copy.deepcopy(self.state), 
            "chat_messages": copy.deepcopy(self.history["chat_messages"]), 
            "context_history": copy.deepcopy(self.history["context_history"])
        }
        self.snapshots.append(snap)
        if len(self.snapshots) > 20: self.snapshots.pop(0)

    def rollback(self):
        if self.snapshots:
            snap = self.snapshots.pop()
            self.state = snap["state"]
            self.history["chat_messages"] = snap["chat_messages"]
            self.history["context_history"] = snap["context_history"]
            return True
        return False

    def export_save_data(self):
        return {
            "save_name": self.save_name, 
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "save_dir_path": self.save_dir_path,
            "description": self.description,
            "state": self.state, "history": self.history, "word_limit": self.word_limit,
            "undercurrent": self.undercurrent.export_state(), "snapshots": self.snapshots
        }

    def load_save_data(self, data):
        self.save_name = data.get('save_name', '')
        self.save_dir_path = data.get('save_dir_path', '')
        self.description = data.get('description', '')
        self.state, self.history = data.get('state', self.state), data.get('history', self.history)
        self.word_limit = data.get('word_limit', 500)
        self.undercurrent.load_state(data.get('undercurrent', {}))
        self.snapshots = data.get('snapshots', [])