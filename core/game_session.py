# core/game_session.py
import copy
from datetime import datetime
from core.undercurrent import UndercurrentEngine
from core.resolution_engine import DualTrackResolver

class GameSession:
    def __init__(self, ai_engine, save_name=""):
        self.ai_engine = ai_engine
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.save_name = save_name
        self.is_game_over = False
        self.char_info = ""
        self.style_info = ""
        self.world_info_base = ""
        self.world_entries = []
        self.word_limit = 500
        
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

    def start_new_game(self, char_data, style_content, world_data, opening):
        self.char_info = char_data.get('description', '')
        self.style_info = style_content
        self.world_info_base = world_data.get('global_setting', '无')
        self.world_entries = world_data.get('entries', [])
        hp, mp = char_data.get('initial_hp', 100), char_data.get('initial_mana', 100)
        self.state['player'] = {"hp": hp, "max_hp": hp, "mana": mp, "max_mana": mp}
        self.history["chat_messages"] = [{"role": "ai", "content": opening}]
        self.history["context_history"] = [opening]

    def process_turn(self, user_action: str):
        self._take_snapshot()
        self.history["chat_messages"].append({"role": "user", "content": user_action})
        
        result = self.resolver.resolve(self, user_action)
        if not result or not result.get('settlement'): return {"error": True}
            
        settlement = result['settlement']
        self.history["chat_messages"].append({"role": "reactions", "content": result['reactions']})
        self.history["chat_messages"].append({"role": "system", "content": f"命运变数: {result['chosen_reaction']['description']}"})
        
        # 【修复】强制处理换行符，防止 AI 传输 \\n
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

    def get_context_text(self): return "\n".join(self.history["context_history"][-3:])
    def get_dynamic_state_for_ai(self): return {"stats": self.state['player'], "bars": self.state['bars'], "properties": self.state['properties'], "buffs": self.state['buffs'], "npcs": self.state['npcs']}
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
                
        # 【修复 Q3】将 NPC 和 属性 的嵌套字典强制转化为字符串！
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
        snap = {"state": copy.deepcopy(self.state), "chat_messages": copy.deepcopy(self.history["chat_messages"]), "context_history": copy.deepcopy(self.history["context_history"])}
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
            "save_name": self.save_name, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "char_info": self.char_info, "style_info": self.style_info,
            "world_info_base": self.world_info_base, "world_entries": self.world_entries,
            "state": self.state, "history": self.history, "word_limit": self.word_limit,
            "undercurrent": self.undercurrent.export_state(), "snapshots": self.snapshots
        }

    def load_save_data(self, data):
        self.save_name = data.get('save_name', '')
        self.char_info, self.style_info = data.get('char_info', ''), data.get('style_info', '')
        self.world_info_base, self.world_entries = data.get('world_info_base', ''), data.get('world_entries', [])
        self.state, self.history = data.get('state', self.state), data.get('history', self.history)
        self.word_limit = data.get('word_limit', 500)
        self.undercurrent.load_state(data.get('undercurrent', {}))
        self.snapshots = data.get('snapshots', [])