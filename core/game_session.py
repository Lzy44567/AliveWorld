# core/game_session.py
import copy, json, random
from datetime import datetime
from core.undercurrent import UndercurrentEngine
from core.resolution_engine import DualTrackResolver
from core.state_manager import StateManager
from core.context_manager import ContextManager
from core.ai_engine import robust_json_parse, intelligent_salvage
from core.entity_repository import EntityRepository
from core.story_settings import normalize_story_settings

class GameSession:
    def __init__(self, ai_engine, save_name="", save_dir_path="", story_settings=None):
        self.ai_engine = ai_engine
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.save_name, self.save_dir_path = save_name, save_dir_path
        self.world_premise, self.plot_compass = "", ""
        self.story_settings = normalize_story_settings(story_settings)
        self.is_game_over = False
        self.word_limit = 500
        
        self.state_mgr = StateManager()
        self.ctx_mgr = ContextManager()
        self.undercurrent = UndercurrentEngine(self.ai_engine)
        self.entity_repository = EntityRepository(self.save_dir_path)
        self.resolver = DualTrackResolver()
        
        self.history = {"chat_messages": [], "context_history": []}
        self.snapshots = [] 

    @property
    def state(self): return self.state_mgr.state
    @property
    def char_info(self): return self.ctx_mgr.char_info
    @property
    def style_info(self): return self.ctx_mgr.style_info
    @property
    def description(self):
        """Compatibility alias for older API consumers and saves."""
        return self.world_premise

    @description.setter
    def description(self, value):
        self.world_premise = value or ""

    def build_active_world_info(self, action):
        return self.ctx_mgr.build_active_world_info(self.get_context_text(), action, self.undercurrent.get_ledger_context())
    def get_dynamic_state_for_ai(self): return self.state_mgr.get_dynamic_state()
    def get_context_text(self): return "\n".join(self.history["context_history"][-3:])

    def start_new_game(self, world_premise, opening):
        self.world_premise = world_premise
        self.history["chat_messages"] = [{"role": "ai", "content": opening}]
        self.history["context_history"] = [opening]

    def _sync_entities_to_local(self):
        self.undercurrent.sync_influence_refs()
        self.entity_repository.synchronize(self.undercurrent.entities)

    def _refresh_local_context(self):
        self.ctx_mgr.refresh_from_local(self.save_dir_path, self.world_premise)
        self.undercurrent.entities = self.entity_repository.load()

    def process_turn(self, user_action: str):
        self._take_snapshot()
        self.undercurrent.causal_ledger.advance_turn()
        self.history["chat_messages"].append({"role": "user", "content": user_action})
        self._refresh_local_context()
        
        result = self.resolver.resolve(self, user_action)
        if not result or not result.get('settlement'): return {"error": True}
            
        settlement = result['settlement']
        resolutions = settlement.get("resolved_influences", [])
        resolved_items = self.undercurrent.causal_ledger.resolve(resolutions)
        self.history["chat_messages"].append({"role": "reactions", "content": result['reactions']})
        self.history["chat_messages"].append({"role": "influence_checks", "content": result.get("triggered_influences", [])})
        self.history["chat_messages"].append({"role": "system", "content": f"命运变数: {result['chosen_reaction']['description']}"})
        
        story_text = settlement.get('story_text', '').replace('\\n', '\n')
        self.history["chat_messages"].append({"role": "ai", "content": story_text})
        resolution_by_id = {item.get("id"): item for item in resolutions if isinstance(item, dict)}
        for influence in resolved_items:
            resolution = resolution_by_id.get(influence.id, {})
            self.history["chat_messages"].append({
                "role": "influence",
                "content": {"id": influence.id, "summary": influence.summary, "result": resolution.get("result", "已在正文兑现")},
            })
        
        # 🚀 修复实体延迟1回合Bug：手动把当前回合刚发生的剧情喂给 Overseer
        active_world, _ = self.build_active_world_info(user_action)
        current_context = active_world + f"\n\n【本回合】\n玩家：{user_action}\n结果：{story_text}"
        world_time = str(settlement.get("status_updates", {}).get("当前时间") or self.state_mgr.state.get("properties", {}).get("当前时间", ""))
        events = self.undercurrent.tick(current_context, enabled=self.story_settings["entitiesEnabled"], world_time=world_time)
        
        self._sync_entities_to_local()
        for ev in events: self.history["chat_messages"].append({"role": "undercurrent", "content": f"🌌 潜流涌动: {ev}"})
        
        self.state_mgr.apply_updates(settlement)
        self.history["context_history"].append(f"玩家：{user_action}\n结果：{story_text}")
        return result

    def reroll_turn(self):
        if not self.snapshots: return {"error": True}
        
        action, reactions, old_desc, triggered_influences = "", [], "", []
        for msg in reversed(self.history["chat_messages"]):
            if msg.get("role") == "user" and not action: action = msg.get("content")
            if msg.get("role") == "reactions" and not reactions: reactions = msg.get("content")
            if msg.get("role") == "influence_checks" and not triggered_influences: triggered_influences = msg.get("content")
            if msg.get("role") == "system" and "命运变数" in msg.get("content", "") and not old_desc: old_desc = msg["content"].replace("命运变数: ", "")
            if action and reactions and old_desc: break 
        
        if not action or not reactions: return {"error": True}
        
        self.rollback()
        self._take_snapshot()
        self.undercurrent.causal_ledger.advance_turn()
        self.history["chat_messages"].append({"role": "user", "content": action})
        
        valid_reactions = [r for r in reactions if r['description'] != old_desc]
        if not valid_reactions: valid_reactions = reactions
        chosen = random.choices(valid_reactions, weights=[p.get('weight', 50) for p in valid_reactions], k=1)[0]
        
        self.history["chat_messages"].append({"role": "reactions", "content": reactions})
        self.history["chat_messages"].append({"role": "influence_checks", "content": triggered_influences})
        self.history["chat_messages"].append({"role": "system", "content": f"命运变数: {chosen['description']}"})
        
        self._refresh_local_context()
        active_world, _ = self.build_active_world_info(action)
        
        from core.prompts import load_system_prompts
        pts = load_system_prompts()
        settle_p = pts.get('settlement_prompt', '').replace('{world_info}', active_world).replace('{character_info}', self.ctx_mgr.char_info).replace('{style_info}', self.ctx_mgr.style_info)
        influence_instruction = "\n".join(
            f"- [{item['id']}] {item['summary']}；必须体现的后果：{item['effect']}；依据：{item['reason']}"
            for item in triggered_influences
        ) or "（本回合没有满足条件的暗流影响）"
        usr_p2 = f"【情景】：\n{self.get_context_text()}\n【状态】：{json.dumps(self.state_mgr.get_dynamic_state(), ensure_ascii=False)}\n【行动】：{action}\n【裁定变数】：{chosen['description']}\n【本回合必须兑现的暗流影响】：\n{influence_instruction}"
        
        raw_settle, err2 = self.ai_engine.chat_json(settle_p, usr_p2, temp=0.8, max_tokens=3000, trace_label="剧情重写")
        settlement = intelligent_salvage("", "网络拦截") if err2 else (robust_json_parse(raw_settle) if raw_settle else intelligent_salvage("", "空返回"))
        resolutions = settlement.get("resolved_influences", [])
        resolved_items = self.undercurrent.causal_ledger.resolve(resolutions)
            
        story_text = settlement.get('story_text', '').replace('\\n', '\n')
        self.history["chat_messages"].append({"role": "ai", "content": story_text})
        resolution_by_id = {item.get("id"): item for item in resolutions if isinstance(item, dict)}
        for influence in resolved_items:
            self.history["chat_messages"].append({"role": "influence", "content": {
                "id": influence.id, "summary": influence.summary,
                "result": resolution_by_id.get(influence.id, {}).get("result", "已在正文兑现"),
            }})
        
        # 🚀 修复实体延迟1回合Bug
        active_world, _ = self.build_active_world_info(action)
        current_context = active_world + f"\n\n【本回合】\n玩家：{action}\n结果：{story_text}"
        world_time = str(settlement.get("status_updates", {}).get("当前时间") or self.state_mgr.state.get("properties", {}).get("当前时间", ""))
        events = self.undercurrent.tick(current_context, enabled=self.story_settings["entitiesEnabled"], world_time=world_time)
        
        self._sync_entities_to_local()
        for ev in events: self.history["chat_messages"].append({"role": "undercurrent", "content": f"🌌 潜流涌动: {ev}"})
                
        self.state_mgr.apply_updates(settlement)
        self.history["context_history"].append(f"玩家：{action}\n结果：{story_text}")
        return {"chat_messages": self.history["chat_messages"], "state": self.state}
    
    def _take_snapshot(self):
        self.snapshots.append({
            "state": copy.deepcopy(self.state), "chat_messages": copy.deepcopy(self.history["chat_messages"]), 
            "context_history": copy.deepcopy(self.history["context_history"]), "undercurrent": self.undercurrent.export_state()
        })
        if len(self.snapshots) > 20: self.snapshots.pop(0)

    def rollback(self):
        if not self.snapshots: return False
        snap = self.snapshots.pop()
        self.state_mgr.state = snap["state"]
        self.history["chat_messages"] = snap["chat_messages"]
        self.history["context_history"] = snap["context_history"]
        self.undercurrent.load_state(snap.get("undercurrent", {}))
        self._sync_entities_to_local()
        return True

    def export_save_data(self):
        return {
            "save_name": self.save_name, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "save_dir_path": self.save_dir_path, "description": self.world_premise, "world_premise": self.world_premise,
            "plot_compass": self.plot_compass, "story_settings": self.story_settings, "word_limit": self.word_limit,
            "state": self.state, "history": self.history, "undercurrent": self.undercurrent.export_state(), "snapshots": self.snapshots
        }

    def load_save_data(self, data):
        self.save_name, self.save_dir_path = data.get('save_name', ''), data.get('save_dir_path', '')
        self.world_premise = data.get('world_premise', data.get('description', ''))
        self.plot_compass = data.get('plot_compass', '')
        self.story_settings = normalize_story_settings(data.get('story_settings'))
        self.entity_repository = EntityRepository(self.save_dir_path)
        self.state_mgr.state, self.history = data.get('state', self.state), data.get('history', self.history)
        self.undercurrent.load_state(data.get('undercurrent', {}))
        self.snapshots = data.get('snapshots', [])
