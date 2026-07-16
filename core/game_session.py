# core/game_session.py
import copy, json
from datetime import datetime
from core.undercurrent import UndercurrentEngine
from core.resolution_engine import DualTrackResolver
from core.state_manager import StateManager
from core.context_manager import ContextManager
from core.ai_engine import robust_json_parse
from core.model_response import failure_message, format_story_text
from core.entity_repository import EntityRepository
from core.story_settings import normalize_story_settings
from core.future_candidates import choose_candidate, normalize_candidates
from core.worldbook_capture import WorldbookCaptureService, capture_requested
from core.chat_messages import ensure_message_ids
from core.action_suggestions import action_suggestion_instruction, normalize_action_suggestions, resolve_action_reference
from core.story_memory import StoryMemoryManager, normalize_story_turns
from utils.sys_logger import get_logger

log = get_logger()

class GameSession:
    def __init__(self, ai_engine, save_name="", save_dir_path="", story_settings=None, memory_ai_engine=None, memory_config=None):
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
        self.worldbook_capture = WorldbookCaptureService(self.ai_engine)
        memory_config = memory_config or {}
        self.story_memory = StoryMemoryManager(
            self.save_dir_path,
            memory_ai_engine or self.ai_engine,
            context_limit=memory_config.get("context_limit", 32768),
        )
        
        self.history = {"chat_messages": [], "context_history": [], "story_turns": []}
        self.action_suggestions = []
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

    def build_visible_world_info(self, action):
        """Worldbook context for subsystems that must not see hidden entity state."""
        return self.ctx_mgr.build_visible_world_info(self.get_context_text(), action)
    def get_dynamic_state_for_ai(self): return self.state_mgr.get_dynamic_state()
    def get_context_text(self):
        return self.story_memory.build_context(
            self.history.get("story_turns", []),
            compression_enabled=self.story_settings.get("autoCompressMemory", False),
        )

    def start_new_game(self, world_premise, opening):
        self.world_premise = world_premise
        self.history["chat_messages"] = [{"role": "ai", "content": opening}]
        ensure_message_ids(self.history["chat_messages"])
        self.history["context_history"] = [opening]
        self.history["story_turns"] = [{
            "turn_id": 0,
            "player": "",
            "story": opening,
            "text": opening,
        }]

    def _sync_entities_to_local(self):
        self.undercurrent.sync_influence_refs()
        self.entity_repository.synchronize(self.undercurrent.entities)

    def _refresh_local_context(self):
        self.ctx_mgr.refresh_from_local(self.save_dir_path, self.world_premise)
        self.undercurrent.entities = self.entity_repository.load()

    def _update_action_suggestions(self, settlement):
        self.action_suggestions = normalize_action_suggestions(
            settlement.get("action_suggestions", []), enabled=self.story_settings["aiSuggestions"]
        )
        log.info("玩家行动建议: count=%s items=%s", len(self.action_suggestions), self.action_suggestions)
        return self.action_suggestions

    def _latest_story_message_ids(self):
        ensure_message_ids(self.history.get("chat_messages", []))
        found = {}
        for message in reversed(self.history.get("chat_messages", [])):
            role = message.get("role")
            if role in {"user", "ai"} and role not in found:
                found[role] = message.get("id")
            if len(found) == 2:
                break
        return [found[role] for role in ("user", "ai") if found.get(role)]

    def process_turn(self, user_action: str):
        self._take_snapshot()
        self.story_memory.schedule(
            self.history.get("story_turns", []),
            enabled=self.story_settings.get("autoCompressMemory", False),
        )
        self.undercurrent.causal_ledger.advance_turn()
        self.history["chat_messages"].append({"role": "user", "content": user_action})
        interpreted_action = resolve_action_reference(user_action, self.action_suggestions)
        if interpreted_action != user_action:
            log.info("玩家行动引用已展开: input=%s resolved=%s", user_action, interpreted_action)
        self._refresh_local_context()
        
        result = self.resolver.resolve(self, interpreted_action)
        if not result or result.get("error") or not result.get('settlement'):
            self.rollback()
            return result or {"error": True, "message": "推演未完成，本回合未保存。"}
            
        settlement = result['settlement']
        resolutions = settlement.get("resolved_influences", [])
        triggered_ids = {item.get("id") for item in result.get("triggered_influences", []) if isinstance(item, dict)}
        resolved_items = self.undercurrent.causal_ledger.resolve(resolutions, allowed_ids=triggered_ids)
        self.history["chat_messages"].append({"role": "reactions", "content": result['reactions']})
        self.history["chat_messages"].append({"role": "influence_checks", "content": result.get("triggered_influences", [])})
        self.history["chat_messages"].append({"role": "system", "content": f"命运变数: {result['chosen_reaction']['description']}"})
        
        story_text = format_story_text(settlement.get('story_text', ''))
        if not story_text:
            self.rollback()
            return {"error": True, "message": failure_message(empty=True)}
        self._update_action_suggestions(settlement)
        self.history["chat_messages"].append({"role": "ai", "content": story_text, "suggestions": self.action_suggestions})
        resolution_by_id = {item.get("id"): item for item in resolutions if isinstance(item, dict)}
        for influence in resolved_items:
            resolution = resolution_by_id.get(influence.id, {})
            self.history["chat_messages"].append({
                "role": "influence",
                "content": {"id": influence.id, "summary": influence.summary, "result": resolution.get("result", "已在正文兑现")},
            })
        
        # 🚀 修复实体延迟1回合Bug：手动把当前回合刚发生的剧情喂给 Overseer
        active_world, _ = self.build_active_world_info(interpreted_action)
        current_context = active_world + f"\n\n【本回合】\n玩家：{interpreted_action}\n结果：{story_text}"
        world_time = str(settlement.get("status_updates", {}).get("当前时间") or self.state_mgr.state.get("properties", {}).get("当前时间", ""))
        events = self.undercurrent.tick(current_context, enabled=self.story_settings["entitiesEnabled"], world_time=world_time)
        
        self._sync_entities_to_local()
        for ev in events: self.history["chat_messages"].append({"role": "undercurrent", "content": f"🌌 潜流涌动: {ev}"})
        
        self.state_mgr.apply_updates(settlement)
        self.history["context_history"].append(f"玩家：{interpreted_action}\n结果：{story_text}")
        self.story_memory.append_turn(
            self.history.setdefault("story_turns", []), interpreted_action, story_text,
            source_message_ids=self._latest_story_message_ids(),
        )
        if self.story_settings["worldbookCaptureEnabled"] and capture_requested(settlement):
            self.worldbook_capture.schedule(
                self.save_dir_path, interpreted_action, story_text,
                review_all=self.story_settings["worldbookCaptureReview"],
            )
        self.story_memory.schedule(
            self.history.get("story_turns", []),
            enabled=self.story_settings.get("autoCompressMemory", False),
        )
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
        interpreted_action = resolve_action_reference(action, self.action_suggestions)
        self._take_snapshot()
        self.undercurrent.causal_ledger.advance_turn()
        self.history["chat_messages"].append({"role": "user", "content": action})
        
        reactions = normalize_candidates(reactions)
        chosen = choose_candidate(reactions, exclude_description=old_desc)
        
        self.history["chat_messages"].append({"role": "reactions", "content": reactions})
        self.history["chat_messages"].append({"role": "influence_checks", "content": triggered_influences})
        self.history["chat_messages"].append({"role": "system", "content": f"命运变数: {chosen['description']}"})
        
        self._refresh_local_context()
        active_world, _ = self.build_active_world_info(interpreted_action)
        
        from core.prompts import load_system_prompts
        pts = load_system_prompts()
        visible_world, _ = self.build_visible_world_info(interpreted_action)
        settle_p = pts.get('settlement_prompt', '').replace('{world_info}', visible_world).replace('{character_info}', self.ctx_mgr.char_info).replace('{style_info}', self.ctx_mgr.style_info)
        suggestion_prompt = action_suggestion_instruction(self.story_settings.get("aiSuggestions", True))
        if suggestion_prompt:
            settle_p += "\n\n【玩家行动建议要求】\n" + suggestion_prompt
        influence_instruction = "\n".join(
            f"- [{item['id']}] {item['summary']}；必须体现的后果：{item['effect']}；依据：{item['reason']}"
            for item in triggered_influences
        ) or "（本回合没有满足条件的暗流影响）"
        usr_p2 = f"【情景】：\n{self.get_context_text()}\n【状态】：{json.dumps(self.state_mgr.get_dynamic_state(), ensure_ascii=False)}\n【行动】：{interpreted_action}\n【裁定变数】：{chosen['description']}\n【本回合必须兑现的暗流影响】：\n{influence_instruction}"

        raw_settle, err2 = self.ai_engine.chat_json(settle_p, usr_p2, temp=0.8, max_tokens=3000, trace_label="剧情重写")
        if err2 or not raw_settle:
            self.rollback()
            return {"error": True, "message": failure_message(err2, empty=not raw_settle and not err2)}
        try:
            settlement = robust_json_parse(raw_settle)
        except Exception:
            self.rollback()
            return {"error": True, "message": failure_message(invalid=True)}
        resolutions = settlement.get("resolved_influences", [])
        triggered_ids = {item.get("id") for item in triggered_influences if isinstance(item, dict)}
        resolved_items = self.undercurrent.causal_ledger.resolve(resolutions, allowed_ids=triggered_ids)
            
        story_text = format_story_text(settlement.get('story_text', ''))
        self._update_action_suggestions(settlement)
        self.history["chat_messages"].append({"role": "ai", "content": story_text, "suggestions": self.action_suggestions})
        resolution_by_id = {item.get("id"): item for item in resolutions if isinstance(item, dict)}
        for influence in resolved_items:
            self.history["chat_messages"].append({"role": "influence", "content": {
                "id": influence.id, "summary": influence.summary,
                "result": resolution_by_id.get(influence.id, {}).get("result", "已在正文兑现"),
            }})
        
        # 🚀 修复实体延迟1回合Bug
        active_world, _ = self.build_active_world_info(interpreted_action)
        current_context = active_world + f"\n\n【本回合】\n玩家：{interpreted_action}\n结果：{story_text}"
        world_time = str(settlement.get("status_updates", {}).get("当前时间") or self.state_mgr.state.get("properties", {}).get("当前时间", ""))
        events = self.undercurrent.tick(current_context, enabled=self.story_settings["entitiesEnabled"], world_time=world_time)
        
        self._sync_entities_to_local()
        for ev in events: self.history["chat_messages"].append({"role": "undercurrent", "content": f"🌌 潜流涌动: {ev}"})
                
        self.state_mgr.apply_updates(settlement)
        self.history["context_history"].append(f"玩家：{interpreted_action}\n结果：{story_text}")
        self.story_memory.append_turn(
            self.history.setdefault("story_turns", []), interpreted_action, story_text,
            source_message_ids=self._latest_story_message_ids(),
        )
        self.story_memory.schedule(
            self.history.get("story_turns", []),
            enabled=self.story_settings.get("autoCompressMemory", False),
        )
        return {"chat_messages": self.history["chat_messages"], "state": self.state, "action_suggestions": self.action_suggestions}
    
    def _take_snapshot(self):
        self.snapshots.append({
            "state": copy.deepcopy(self.state), "chat_messages": copy.deepcopy(self.history["chat_messages"]), 
            "context_history": copy.deepcopy(self.history["context_history"]), "undercurrent": self.undercurrent.export_state(),
            "story_turns": copy.deepcopy(self.history.get("story_turns", [])),
            "action_suggestions": copy.deepcopy(self.action_suggestions)
        })
        if len(self.snapshots) > 20: self.snapshots.pop(0)

    def rollback(self):
        if not self.snapshots: return False
        snap = self.snapshots.pop()
        self.state_mgr.state = snap["state"]
        self.history["chat_messages"] = snap["chat_messages"]
        self.history["context_history"] = snap["context_history"]
        self.history["story_turns"] = snap.get("story_turns") or normalize_story_turns(snap.get("context_history", []))
        self.undercurrent.load_state(snap.get("undercurrent", {}))
        self.action_suggestions = snap.get("action_suggestions", [])
        self._sync_entities_to_local()
        return True

    def export_save_data(self):
        ensure_message_ids(self.history.get("chat_messages", []))
        return {
            "save_name": self.save_name, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "save_dir_path": self.save_dir_path, "description": self.world_premise, "world_premise": self.world_premise,
            "plot_compass": self.plot_compass, "story_settings": self.story_settings, "word_limit": self.word_limit,
            "state": self.state, "history": self.history, "undercurrent": self.undercurrent.export_state(), "snapshots": self.snapshots,
            "action_suggestions": self.action_suggestions,
            "story_memory": self.story_memory.export_state(),
        }

    def load_save_data(self, data):
        self.save_name, self.save_dir_path = data.get('save_name', ''), data.get('save_dir_path', '')
        self.world_premise = data.get('world_premise', data.get('description', ''))
        self.plot_compass = data.get('plot_compass', '')
        self.story_settings = normalize_story_settings(data.get('story_settings'))
        self.entity_repository = EntityRepository(self.save_dir_path)
        self.state_mgr.state, self.history = data.get('state', self.state), data.get('history', self.history)
        self.history.setdefault("context_history", [])
        if not self.history.get("story_turns"):
            self.history["story_turns"] = normalize_story_turns(self.history.get("context_history", []))
        else:
            self.history["story_turns"] = normalize_story_turns(self.history.get("story_turns", []))
        self.story_memory.set_runtime(save_dir=self.save_dir_path)
        self.story_memory.import_fallback(data.get("story_memory"))
        ensure_message_ids(self.history.get("chat_messages", []))
        self.action_suggestions = normalize_action_suggestions(
            data.get("action_suggestions", []), enabled=self.story_settings["aiSuggestions"]
        )
        if not self.action_suggestions:
            for message in reversed(self.history.get("chat_messages", [])):
                if message.get("role") == "ai":
                    self.action_suggestions = normalize_action_suggestions(
                        message.get("suggestions", []), enabled=self.story_settings["aiSuggestions"]
                    )
                    break
        self.undercurrent.load_state(data.get('undercurrent', {}))
        self.snapshots = data.get('snapshots', [])
