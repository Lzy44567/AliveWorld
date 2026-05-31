# core/game_session.py
import os
import copy
import yaml
import glob
import re
import json
from datetime import datetime
from core.undercurrent import UndercurrentEngine, Entity
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
        self.description = ""
        
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
        if not self.save_dir_path or not os.path.exists(self.save_dir_path): return

        styles = []
        for f in glob.glob(os.path.join(self.save_dir_path, 'styles', '*.yml')):
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and data.get('is_active', True): styles.append(data.get('content', ''))
        self.style_info = "\n---\n".join(styles)

        worlds_base = []
        self.world_entries = []
        for f in glob.glob(os.path.join(self.save_dir_path, 'worldbooks', '*.yml')):
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and data.get('is_active', True):
                    if data.get('global_setting'): worlds_base.append(f"[{data.get('name', '界域法则')}]：{data.get('global_setting')}")
                    self.world_entries.extend(data.get('entries', []))
        self.world_info_base = "\n".join(worlds_base)

        player_chars = []
        npc_chars = []
        for f in glob.glob(os.path.join(self.save_dir_path, 'characters', '*.yml')):
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and data.get('is_active', True):
                    desc = f"[{data.get('name', '未知实体')}]：{data.get('description', '')}"
                    if data.get('is_player', False): player_chars.append(desc)
                    else: npc_chars.append(desc)
        
        self.char_info = "\n---\n".join(player_chars) if player_chars else "无名冒险者"
        if npc_chars: self.world_info_base += "\n\n【当前登场的重要NPC与势力】：\n" + "\n".join(npc_chars)
        if self.description: self.world_info_base = f"【🔥宇宙主导向 (最高法则)】：{self.description}\n\n" + self.world_info_base

        self.undercurrent.entities = []
        for f in glob.glob(os.path.join(self.save_dir_path, 'entities', '*.yml')):
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and data.get('is_active', True):
                    self.undercurrent.entities.append(Entity(name=data.get('name', '未知'), goal=data.get('motive', data.get('description', ''))))

    def _sync_entities_to_local(self):
        if not self.save_dir_path: return
        local_ent_dir = os.path.join(self.save_dir_path, 'entities')
        os.makedirs(local_ent_dir, exist_ok=True)
        active_names = [e.name for e in self.undercurrent.entities]

        for f in glob.glob(os.path.join(local_ent_dir, '*.yml')):
            name = os.path.basename(f).replace('.yml', '')
            if not any(name == re.sub(r'[^\w\s-]', '', an).strip() for an in active_names):
                try: os.remove(f)
                except: pass

        for e in self.undercurrent.entities:
            safe_filename = re.sub(r'[^\w\s-]', '', e.name).strip()
            if not safe_filename: safe_filename = "未命名变数"
            
            fpath = os.path.join(local_ent_dir, f"{safe_filename}.yml")
            data = {}
            if os.path.exists(fpath):
                try:
                    with open(fpath, 'r', encoding='utf-8') as file: data = yaml.safe_load(file) or {}
                except: pass
            
            data['name'] = e.name 
            data['motive'] = e.goal
            data['is_active'] = True
            data['tags'] = data.get('tags', ["暗流势力", "AI衍化"])
            data['description'] = data.get('description', e.goal)
            
            with open(fpath, 'w', encoding='utf-8') as file:
                yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)

    def process_turn(self, user_action: str):
        self._take_snapshot()
        self.history["chat_messages"].append({"role": "user", "content": user_action})
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
        
        self._sync_entities_to_local()
        
        if undercurrent_events:
            for ev in undercurrent_events:
                self.history["chat_messages"].append({"role": "undercurrent", "content": f"🌌 潜流涌动: {ev}"})
        
        self._apply_state_updates(settlement)
        self.history["context_history"].append(f"玩家：{user_action}\n结果：{story_text}")
        
        return result

    # 🚀 新增：专门处理重掷未来的核心逻辑
    def reroll_turn(self):
        if not self.snapshots: return {"error": True}
        
        action = ""
        reactions = []
        for msg in reversed(self.history["chat_messages"]):
            if msg.get("role") == "user": action = msg.get("content")
            if msg.get("role") == "reactions": reactions = msg.get("content")
            if action and reactions: break
            
        if not action or not reactions: return {"error": True}
        
        self.rollback() # 回退到动作发生前
        self._take_snapshot()
        self.history["chat_messages"].append({"role": "user", "content": action})
        
        import random
        chosen = random.choices(reactions, weights=[p.get('weight', 50) for p in reactions], k=1)[0]
        
        self.history["chat_messages"].append({"role": "reactions", "content": reactions})
        self.history["chat_messages"].append({"role": "system", "content": f"命运变数: {chosen['description']}"})
        
        # 仅重新执行结算
        self.refresh_context_from_local()
        active_world, _ = self.build_active_world_info(action)
        
        from core.prompts import load_system_prompts
        pts = load_system_prompts()
        settle_p = pts.get('settlement_prompt', '').replace('{world_info}', active_world).replace('{character_info}', self.char_info).replace('{style_info}', self.style_info)
        
        dyn_state = self.get_dynamic_state_for_ai()
        ctx = self.get_context_text()
        usr_p2 = f"【情景】：\n{ctx}\n【状态】：{json.dumps(dyn_state, ensure_ascii=False)}\n【行动】：{action}\n【裁定变数】：{chosen['description']}"
        
        from core.ai_engine import robust_json_parse, intelligent_salvage
        raw_settle, err2 = self.ai_engine.chat_json(settle_p, usr_p2, temp=0.8, max_tokens=3000)
        
        if err2 or not raw_settle: settlement = intelligent_salvage("", "网络或审查拦截")
        else:
            try: settlement = robust_json_parse(raw_settle)
            except Exception as e: settlement = intelligent_salvage(raw_settle, str(e))
            
        story_text = settlement.get('story_text', '').replace('\\n', '\n')
        self.history["chat_messages"].append({"role": "ai", "content": story_text})
        
        undercurrent_events = self.undercurrent.tick(self.get_context_text())
        self._sync_entities_to_local()
        if undercurrent_events:
            for ev in undercurrent_events:
                self.history["chat_messages"].append({"role": "undercurrent", "content": f"🌌 潜流涌动: {ev}"})
                
        self._apply_state_updates(settlement)
        self.history["context_history"].append(f"玩家：{action}\n结果：{story_text}")
        
        return {"chat_messages": self.history["chat_messages"], "state": self.state}

    def get_context_text(self): return "\n".join(self.history["context_history"][-3:])
        
    def get_dynamic_state_for_ai(self): 
        return { "stats": self.state['player'], "bars": self.state['bars'], "properties": self.state['properties'], "buffs": self.state['buffs'], "npcs": self.state['npcs'] }
        
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
        
        # 🚀 修复问题5：彻底修复了进度条的当前值无法更新的问题
        for bn, bd in result.get('dynamic_bars', {}).items():
            if not isinstance(bd, dict): continue
            if bn not in self.state['bars']: 
                self.state['bars'][bn] = {"current": bd.get('current', 0), "max": bd.get('max', 100)}
            else:
                if 'current' in bd: self.state['bars'][bn]["current"] = bd['current']
                if 'max' in bd: self.state['bars'][bn]["max"] = bd['max']
                if 'change' in bd: self.state['bars'][bn]["current"] = max(0, min(self.state['bars'][bn]["current"] + bd['change'], self.state['bars'][bn]["max"]))
                
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
        snap = { "state": copy.deepcopy(self.state), "chat_messages": copy.deepcopy(self.history["chat_messages"]), "context_history": copy.deepcopy(self.history["context_history"]) }
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
            "save_dir_path": self.save_dir_path, "description": self.description,
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