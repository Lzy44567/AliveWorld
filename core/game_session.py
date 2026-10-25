# core/game_session.py
import copy
import json
from datetime import datetime
from core.undercurrent import UndercurrentEngine
from core.resolution_engine import DualTrackResolver
from core.state_manager import StateManager, StateUpdatePlan
from core.npc_identity import NpcIdentityError
from core.effect_progress import EffectProgressError, needs_effect_progress, prepare_effect_preview, validate_effect_followup
from core.context_manager import ContextManager
from core.ai_engine import robust_json_parse
from core.model_response import failure_message, format_story_text
from core.entity_repository import EntityRepository
from core.story_settings import normalize_story_settings
from core.story_length import normalize_target_story_length
from core.future_candidates import choose_candidate, normalize_candidates
from core.worldbook_capture import WorldbookCaptureService, capture_requested
from core.chat_messages import ensure_message_ids
from core.action_suggestions import normalize_action_suggestions, resolve_action_reference
from core.story_memory import StoryMemoryManager, normalize_story_turns
from core.user_preferences import UserPreferenceRepository
from core.preference_learning import preference_evidence
from core.preference_analysis import PreferenceAnalysisService
from core.player_agency import normalize_action_adjudication
from core.story_prompt_builder import SettlementRequestSnapshot, build_settlement_request
from core.settlement_contract import SettlementContractError, validate_settlement
from core.worldbook_collaboration import default_collaboration, collect_conflicts
from utils.sys_logger import get_logger

log = get_logger()

class GameSession:
    def __init__(
        self,
        ai_engine,
        save_name="",
        save_dir_path="",
        story_settings=None,
        memory_ai_engine=None,
        memory_config=None,
        preference_ai_engine=None,
        overseer_ai_engine=None,
        worldbook_capture_ai_engine=None,
    ):
        self.ai_engine = ai_engine
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.save_name, self.save_dir_path = save_name, save_dir_path
        self.world_premise, self.plot_compass = "", ""
        self.story_settings = normalize_story_settings(story_settings)
        self.is_game_over = False
        self.word_limit = self.story_settings["targetStoryLength"]
        
        self.state_mgr = StateManager()
        self.ctx_mgr = ContextManager()
        self.undercurrent = UndercurrentEngine(overseer_ai_engine or self.ai_engine)
        self.entity_repository = EntityRepository(self.save_dir_path)
        self.resolver = DualTrackResolver()
        self.worldbook_capture = WorldbookCaptureService(worldbook_capture_ai_engine or self.ai_engine)
        self._pending_worldbook_captures = []
        self.worldbook_collaboration = default_collaboration()
        self.user_preferences = UserPreferenceRepository()
        self.preference_analysis = PreferenceAnalysisService(preference_ai_engine or self.ai_engine)
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

    def _overseer_context(self, action, story, state_plan, adjudication, resolutions):
        world, _ = self.build_visible_world_info(action)
        active_names = {e.name for e in self.undercurrent.entities if e.is_active}
        influences = [i.to_dict() for i in self.undercurrent.causal_ledger.influences
                      if i.status == "active" and any(link.get("entity") in active_names for link in i.source_links)]
        return world + "\n【本轮交接】\n" + json.dumps({
            "player_action": action, "story_text": story,
            "state_after_settlement": state_plan.state,
            "adjudication": adjudication, "resolved_influences": resolutions,
            "active_influences": influences,
        }, ensure_ascii=False, sort_keys=True)
    def get_user_preference_context(self):
        if not self.story_settings.get("useUserPreferences", True):
            return ""
        category_settings = {
            "story": "preferenceStoryEnabled", "narrative": "preferenceStoryEnabled",
            "adult": "preferenceAdultEnabled", "action": "preferenceActionEnabled",
            "character": "preferenceCharacterEnabled", "relationship": "preferenceRelationshipEnabled",
            "visual": "preferenceVisualEnabled", "boundary": "preferenceStoryEnabled",
            "content": "preferenceStoryEnabled", "other": "preferenceStoryEnabled",
        }
        enabled = {category for category, setting in category_settings.items() if self.story_settings.get(setting, True)}
        return self.user_preferences.context(categories=enabled)

    def _record_preference_evidence(self, settlement, turn_id, player_action):
        added = self.user_preferences.record_evidence(
            preference_evidence(
                settlement,
                enabled=self.story_settings.get("learnUserPreferences", True),
                player_action=player_action,
            ),
            save_name=self.save_name, turn_id=turn_id,
        )
        if added:
            log.info("玩家偏好行为证据: count=%s ids=%s", len(added), [item.get("id") for item in added])
            self.preference_analysis.schedule(
                self.user_preferences,
                enabled=self.story_settings.get("deepPreferenceAnalysis", True),
                include_sensitive=self.story_settings.get("analyzeSensitivePreferences", False),
            )
        return added

    def record_preference_interaction(
        self, signal_type, summary, context="", *, related_turn_id=None, sensitive=False
    ):
        """Persist a real UI interaction without interpreting the player's motive."""
        if not self.story_settings.get("learnUserPreferences", True):
            return None
        evidence = self.user_preferences.record_interaction(
            signal_type=signal_type,
            summary=summary,
            context=context,
            save_name=self.save_name,
            related_turn_id=related_turn_id,
            sensitive=sensitive,
        )
        if evidence:
            log.info("玩家偏好交互证据: type=%s id=%s", signal_type, evidence.get("id"))
            self.preference_analysis.schedule(
                self.user_preferences,
                enabled=self.story_settings.get("deepPreferenceAnalysis", True),
                include_sensitive=self.story_settings.get("analyzeSensitivePreferences", False),
            )
        return evidence
    def get_context_text(self):
        return self.story_memory.build_context(
            self.history.get("story_turns", []),
            compression_enabled=self.story_settings.get("autoCompressMemory", False),
        )

    def start_new_game(self, world_premise, opening):
        self.world_premise = world_premise
        opening = opening.strip()
        self.history["chat_messages"] = [{"role": "ai", "content": opening}] if opening else []
        ensure_message_ids(self.history["chat_messages"])
        self.history["context_history"] = [opening] if opening else []
        self.history["story_turns"] = [{
            "turn_id": 0,
            "player": "",
            "story": opening,
            "text": opening,
        }] if opening else []

    def _sync_entities_to_local(self):
        self.undercurrent.sync_influence_refs()
        self.entity_repository.synchronize(self.undercurrent.entities)

    def _refresh_local_context(self):
        self.ctx_mgr.refresh_from_local(self.save_dir_path, self.world_premise,
                                       active_turns=self.history.get('story_turns', []),
                                       collaboration=self.worldbook_collaboration)
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

    def process_turn(self, user_action: str, *, on_text_delta=None):
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
        
        result = self.resolver.resolve(self, interpreted_action, **({"on_text_delta": on_text_delta} if on_text_delta is not None else {}))
        if not result or result.get("error") or not result.get('settlement'):
            self.rollback()
            return result or {"error": True, "message": "推演未完成，本回合未保存。"}
            
        settlement = result['settlement']
        conflict_rules = copy.deepcopy(self.ctx_mgr.supplied_world_rules)
        story_text = format_story_text(settlement.get('story_text', ''))
        if not story_text:
            self.rollback()
            return {"error": True, "message": failure_message(empty=True)}
        try:
            state_plan = self.state_mgr.plan_updates(
                settlement, story_text=story_text, player_action=interpreted_action,
                effect_plan=self._effect_state_plan(result.get("effect_preview")),
            )
        except NpcIdentityError as exc:
            self.rollback()
            return {"error": True, "message": f"人物状态未保存：{exc}。"}
        except Exception as exc:
            log.warning("状态更新无法在副本上完成: %s", exc)
            self.rollback()
            return {"error": True, "message": "结算状态无法安全应用，本回合未保存。"}
        resolutions = settlement.get("resolved_influences", [])
        triggered_ids = {item.get("id") for item in result.get("triggered_influences", []) if isinstance(item, dict)}
        resolved_items = self.undercurrent.causal_ledger.resolve(resolutions, allowed_ids=triggered_ids)
        self.history["chat_messages"].append({"role": "reactions", "content": result['reactions']})
        self.history["chat_messages"].append({"role": "action_adjudication", "content": result.get("action_adjudication", {})})
        self.history["chat_messages"].append({"role": "influence_checks", "content": result.get("triggered_influences", [])})
        self.history["chat_messages"].append({"role": "system", "content": f"命运变数: {result['chosen_reaction']['description']}"})
        self._update_action_suggestions(settlement)
        self.history["chat_messages"].append({"role": "ai", "content": story_text, "suggestions": self.action_suggestions})
        if result.get("effect_preview") is not None:
            self.history["chat_messages"][-1]["effect_progress"] = result["effect_preview"]["report"]
        resolution_by_id = {item.get("id"): item for item in resolutions if isinstance(item, dict)}
        for influence in resolved_items:
            resolution = resolution_by_id.get(influence.id, {})
            self.history["chat_messages"].append({
                "role": "influence",
                "content": {"id": influence.id, "summary": influence.summary, "result": resolution.get("result", "已在正文兑现")},
            })
        
        # 🚀 修复实体延迟1回合Bug：手动把当前回合刚发生的剧情喂给 Overseer
        current_context = self._overseer_context(interpreted_action, story_text, state_plan,
                                                 result.get("action_adjudication", {}), resolutions)
        world_time = str(settlement.get("status_updates", {}).get("当前时间") or self.state_mgr.state.get("properties", {}).get("当前时间", ""))
        events = self.undercurrent.tick(current_context, enabled=self.story_settings["entitiesEnabled"], world_time=world_time)
        
        self._sync_entities_to_local()
        for ev in events: self.history["chat_messages"].append({"role": "undercurrent", "content": f"🌌 潜流涌动: {ev}"})
        
        self.state_mgr.commit(state_plan)
        self.history["context_history"].append(f"玩家：{interpreted_action}\n结果：{story_text}")
        self.story_memory.append_turn(
            self.history.setdefault("story_turns", []), interpreted_action, story_text,
            source_message_ids=self._latest_story_message_ids(),
        )
        self._record_preference_evidence(
            settlement, self.history["story_turns"][-1]["turn_id"], interpreted_action
        )
        self._record_worldbook_conflicts(settlement, conflict_rules)
        self._queue_worldbook_capture(settlement, interpreted_action, story_text)
        self.story_memory.schedule(
            self.history.get("story_turns", []),
            enabled=self.story_settings.get("autoCompressMemory", False),
        )
        return result

    def _effect_state_plan(self, preview):
        if preview is None:
            if not needs_effect_progress(self.state):
                return self.state_mgr.plan_effects(0)[0]
            return None
        return StateUpdatePlan(preview["state"], self.state_mgr.export_metadata())

    def reroll_turn(self, *, on_text_delta=None):
        if not self.snapshots: return {"error": True}

        original_runtime = self._capture_runtime()
        original_turn_id = None
        if original_runtime.get("story_turns"):
            original_turn_id = original_runtime["story_turns"][-1].get("turn_id")

        def fail_reroll(payload):
            self._restore_runtime(original_runtime)
            return payload
        
        action, reactions, old_desc, triggered_influences, action_adjudication = "", [], "", [], {}
        for msg in reversed(self.history["chat_messages"]):
            if msg.get("role") == "user" and not action: action = msg.get("content")
            if msg.get("role") == "reactions" and not reactions: reactions = msg.get("content")
            if msg.get("role") == "influence_checks" and not triggered_influences: triggered_influences = msg.get("content")
            if msg.get("role") == "action_adjudication" and not action_adjudication: action_adjudication = msg.get("content")
            if msg.get("role") == "system" and "命运变数" in msg.get("content", "") and not old_desc: old_desc = msg["content"].replace("命运变数: ", "")
            if action and reactions and old_desc: break 
        
        if not action or not reactions: return {"error": True}
        
        # Rewriting restores world state, not the player's current narrative controls.
        plot_compass = self.plot_compass
        preference_settings = {key: value for key, value in self.story_settings.items()
                               if key.startswith("preference") or key == "useUserPreferences"}
        self.rollback(remove_preference_evidence=False)
        self.plot_compass = plot_compass
        self.story_settings.update(preference_settings)
        interpreted_action = resolve_action_reference(action, self.action_suggestions)
        self._take_snapshot()
        self.undercurrent.causal_ledger.advance_turn()
        self.history["chat_messages"].append({"role": "user", "content": action})
        
        reactions = normalize_candidates(
            reactions,
            required_facts=normalize_action_adjudication(action_adjudication)["accepted_facts"],
        )
        chosen = choose_candidate(reactions, exclude_description=old_desc)
        try:
            effect_preview = prepare_effect_preview(self.state_mgr.get_dynamic_state(), chosen.get("effect_progress"))
        except EffectProgressError as exc:
            return fail_reroll({"error": True, "message": f"{exc}，本回合未保存。"})
        settlement_state = effect_preview["state"] if effect_preview is not None else self.state_mgr.get_dynamic_state()
        
        self.history["chat_messages"].append({"role": "reactions", "content": reactions})
        self.history["chat_messages"].append({"role": "action_adjudication", "content": action_adjudication})
        self.history["chat_messages"].append({"role": "influence_checks", "content": triggered_influences})
        self.history["chat_messages"].append({"role": "system", "content": f"命运变数: {chosen['description']}"})
        
        self._refresh_local_context()
        active_world, _ = self.build_active_world_info(interpreted_action)
        
        from core.prompts import load_system_prompts
        from core.world_rule_commands import resolution_instruction
        visible_world, _ = self.build_visible_world_info(interpreted_action)
        conflict_rules = copy.deepcopy(self.ctx_mgr.supplied_world_rules)
        pts = load_system_prompts()
        rule_command_prompt = resolution_instruction(interpreted_action)
        preference_context = self.get_user_preference_context()
        action_adjudication = normalize_action_adjudication(action_adjudication)
        request = build_settlement_request(SettlementRequestSnapshot(
            mode="reroll",
            plot_compass=self.plot_compass,
            baseline_prompt=pts.get("settlement_prompt", ""),
            context_text=self.get_context_text(),
            dynamic_state=settlement_state,
            player_action=interpreted_action,
            visible_world=visible_world,
            character_info=self.ctx_mgr.char_info,
            style_info=self.ctx_mgr.style_info,
            word_limit=self.word_limit,
            story_settings=self.story_settings,
            rule_command_prompt=rule_command_prompt,
            preference_context=preference_context,
            action_adjudication=action_adjudication,
            chosen_description=chosen["description"],
            triggered_influences=triggered_influences,
            effect_report=effect_preview["report"] if effect_preview is not None else None,
            npc_identities=self.state_mgr.npc_identity_context(interpreted_action),
            worldbook_collaboration=bool(self.ctx_mgr.primary_worldbook and len(self.ctx_mgr.world_books) > 1),
        ))
        raw_settle, err2 = self.ai_engine.chat_json(
            request.system_prompt, request.user_prompt,
            temp=request.temperature, max_tokens=request.max_tokens,
            trace_label=request.trace_label, prompt_manifest=request.prompt_manifest,
            **({"on_text_delta": on_text_delta} if on_text_delta is not None else {}),
        )
        if err2 or not raw_settle:
            return fail_reroll({"error": True, "message": failure_message(err2, empty=not raw_settle and not err2)})
        try:
            settlement = robust_json_parse(raw_settle)
        except Exception:
            return fail_reroll({"error": True, "message": failure_message(invalid=True)})
        triggered_ids = {item.get("id") for item in triggered_influences if isinstance(item, dict)}
        try:
            settlement = validate_settlement(
                settlement,
                current_state=settlement_state,
                triggered_ids=triggered_ids,
            )
            validate_effect_followup(settlement, effect_preview)
        except EffectProgressError as exc:
            return fail_reroll({"error": True, "message": f"{exc}，本回合未保存。"})
        except SettlementContractError as exc:
            log.warning("重掷结算契约校验失败: %s", exc)
            return fail_reroll({
                "error": True,
                "message": f"模型返回的结算字段无法安全应用（{exc.path}），本回合未保存。",
            })
        story_text = format_story_text(settlement.get('story_text', ''))
        try:
            state_plan = self.state_mgr.plan_updates(
                settlement, story_text=story_text, player_action=interpreted_action,
                effect_plan=self._effect_state_plan(effect_preview),
            )
        except NpcIdentityError as exc:
            return fail_reroll({"error": True, "message": f"人物状态未保存：{exc}。"})
        except Exception as exc:
            log.warning("重掷状态无法在副本上完成: %s", exc)
            return fail_reroll({"error": True, "message": "结算状态无法安全应用，本回合未保存。"})
        resolutions = settlement.get("resolved_influences", [])
        resolved_items = self.undercurrent.causal_ledger.resolve(resolutions, allowed_ids=triggered_ids)

        self._update_action_suggestions(settlement)
        self.history["chat_messages"].append({"role": "ai", "content": story_text, "suggestions": self.action_suggestions})
        if effect_preview is not None:
            self.history["chat_messages"][-1]["effect_progress"] = effect_preview["report"]
        resolution_by_id = {item.get("id"): item for item in resolutions if isinstance(item, dict)}
        for influence in resolved_items:
            self.history["chat_messages"].append({"role": "influence", "content": {
                "id": influence.id, "summary": influence.summary,
                "result": resolution_by_id.get(influence.id, {}).get("result", "已在正文兑现"),
            }})
        
        # 🚀 修复实体延迟1回合Bug
        current_context = self._overseer_context(interpreted_action, story_text, state_plan,
                                                 action_adjudication, resolutions)
        world_time = str(settlement.get("status_updates", {}).get("当前时间") or self.state_mgr.state.get("properties", {}).get("当前时间", ""))
        events = self.undercurrent.tick(current_context, enabled=self.story_settings["entitiesEnabled"], world_time=world_time)
        
        self._sync_entities_to_local()
        for ev in events: self.history["chat_messages"].append({"role": "undercurrent", "content": f"🌌 潜流涌动: {ev}"})
                
        self.state_mgr.commit(state_plan)
        self.history["context_history"].append(f"玩家：{interpreted_action}\n结果：{story_text}")
        self.story_memory.append_turn(
            self.history.setdefault("story_turns", []), interpreted_action, story_text,
            source_message_ids=self._latest_story_message_ids(),
        )
        if original_turn_id is not None:
            self.user_preferences.remove_turn_evidence(
                save_name=self.save_name, turn_id=original_turn_id,
            )
        self._record_preference_evidence(
            settlement, self.history["story_turns"][-1]["turn_id"], interpreted_action
        )
        self._record_worldbook_conflicts(settlement, conflict_rules)
        self._queue_worldbook_capture(settlement, interpreted_action, story_text)
        self.story_memory.schedule(
            self.history.get("story_turns", []),
            enabled=self.story_settings.get("autoCompressMemory", False),
        )
        return {"chat_messages": self.history["chat_messages"], "state": self.state, "action_suggestions": self.action_suggestions}
    
    def _record_worldbook_conflicts(self, settlement, supplied_rules):
        self.worldbook_collaboration, count = collect_conflicts(
            settlement.get("worldbook_conflicts"), state=self.worldbook_collaboration,
            books=self.ctx_mgr.world_books, supplied_rules=supplied_rules,
            source_turn=self.history["story_turns"][-1], active_turns=self.history["story_turns"],
        )
        if count:
            self.history["chat_messages"][-1]["worldbook_conflict_count"] = count

    def _queue_worldbook_capture(self, settlement, action, story):
        if self.story_settings["worldbookCaptureEnabled"] and capture_requested(settlement, action):
            self._pending_worldbook_captures.append({
                "player_action": action, "story_text": story,
                "review_all": self.story_settings["worldbookCaptureReview"],
                "world_change_events": copy.deepcopy(settlement.get("world_change_events")),
                "source_turn": copy.deepcopy(self.history["story_turns"][-1]),
            })

    def dispatch_committed_worldbook_captures(self):
        """Called only after the API transaction has durably saved this story."""
        pending, self._pending_worldbook_captures = self._pending_worldbook_captures, []
        for task in pending:
            try:
                self.worldbook_capture.schedule(self.save_dir_path, **task)
            except Exception as exc:
                log.warning("正文已保存；世界书捕获调度失败: %s", exc)

    def _snapshot_payload(self):
        return {
            "state": copy.deepcopy(self.state), "chat_messages": copy.deepcopy(self.history["chat_messages"]), 
            "context_history": copy.deepcopy(self.history["context_history"]), "undercurrent": self.undercurrent.export_state(),
            "story_turns": copy.deepcopy(self.history.get("story_turns", [])),
            "action_suggestions": copy.deepcopy(self.action_suggestions),
            "state_meta": copy.deepcopy(self.state_mgr.export_metadata()),
        }

    def _take_snapshot(self):
        self.snapshots.append(self._snapshot_payload())
        if len(self.snapshots) > 20: self.snapshots.pop(0)

    def _capture_runtime(self):
        payload = self._snapshot_payload()
        payload["snapshots"] = copy.deepcopy(self.snapshots)
        payload["preferences"] = self.user_preferences.export_state()
        payload["plot_compass"] = self.plot_compass
        payload["story_settings"] = copy.deepcopy(self.story_settings)
        payload["word_limit"] = self.word_limit
        payload["is_game_over"] = self.is_game_over
        payload["pending_worldbook_captures"] = copy.deepcopy(self._pending_worldbook_captures)
        payload["worldbook_collaboration"] = copy.deepcopy(self.worldbook_collaboration)
        return payload

    def _restore_runtime(self, snap):
        if "worldbook_collaboration" in snap:
            self.worldbook_collaboration = copy.deepcopy(snap["worldbook_collaboration"])
        self._pending_worldbook_captures = copy.deepcopy(snap.get("pending_worldbook_captures", []))
        self.state_mgr.state = copy.deepcopy(snap["state"])
        self.state_mgr.load_metadata(copy.deepcopy(snap.get("state_meta")))
        self.history["chat_messages"] = copy.deepcopy(snap["chat_messages"])
        self.history["context_history"] = copy.deepcopy(snap["context_history"])
        self.history["story_turns"] = copy.deepcopy(snap.get("story_turns", []))
        self.undercurrent.load_state(copy.deepcopy(snap.get("undercurrent", {})))
        self.action_suggestions = copy.deepcopy(snap.get("action_suggestions", []))
        if "snapshots" in snap:
            self.snapshots = copy.deepcopy(snap["snapshots"])
        if "preferences" in snap:
            self.user_preferences.restore_state(copy.deepcopy(snap["preferences"]))
        if "plot_compass" in snap:
            self.plot_compass = snap["plot_compass"]
        if "story_settings" in snap:
            self.story_settings = copy.deepcopy(snap["story_settings"])
        if "word_limit" in snap:
            self.word_limit = snap["word_limit"]
        if "is_game_over" in snap:
            self.is_game_over = snap["is_game_over"]
        self._sync_entities_to_local()

    def capture_transaction_state(self):
        return self._capture_runtime()

    def restore_transaction_state(self, snapshot):
        self._restore_runtime(snapshot)

    def rollback(self, *, remove_preference_evidence=True):
        if not self.snapshots: return False
        snap = self.snapshots.pop()
        snapshot_turn_ids = {int(turn.get("turn_id", -1)) for turn in snap.get("story_turns", [])}
        removed_turn_ids = {
            int(turn.get("turn_id", -1)) for turn in self.history.get("story_turns", [])
        } - snapshot_turn_ids
        if remove_preference_evidence:
            for turn_id in removed_turn_ids:
                self.user_preferences.remove_turn_evidence(save_name=self.save_name, turn_id=turn_id)
        if not snap.get("story_turns"):
            snap["story_turns"] = normalize_story_turns(snap.get("context_history", []))
        self._restore_runtime(snap)
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
            "worldbook_collaboration": self.worldbook_collaboration,
            "state_meta": self.state_mgr.export_metadata(),
        }

    def load_save_data(self, data, *, save_dir_path=None):
        # The current runtime directory is authoritative. Persisted absolute
        # paths become stale after migration, ZIP extraction, cloning or moves.
        runtime_save_dir = str(save_dir_path or self.save_dir_path or data.get('save_dir_path', ''))
        self.save_name, self.save_dir_path = data.get('save_name', ''), runtime_save_dir
        self.world_premise = data.get('world_premise', data.get('description', ''))
        self.plot_compass = data.get('plot_compass', '')
        self.worldbook_collaboration = {**default_collaboration(), **data.get('worldbook_collaboration', {})}
        legacy_settings = dict(data.get('story_settings') or {})
        if "targetStoryLength" not in legacy_settings and data.get("word_limit") is not None:
            legacy_settings["targetStoryLength"] = data.get("word_limit")
        self.story_settings = normalize_story_settings(legacy_settings)
        self.word_limit = normalize_target_story_length(self.story_settings["targetStoryLength"])
        self.entity_repository = EntityRepository(self.save_dir_path)
        self.state_mgr.state, self.history = data.get('state', self.state), data.get('history', self.history)
        self.state_mgr.load_metadata(data.get("state_meta"))
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
