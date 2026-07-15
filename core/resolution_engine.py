# core/resolution_engine.py
import json
from utils.sys_logger import get_logger
from core.prompts import load_system_prompts
from core.ai_engine import robust_json_parse
from core.model_response import failure_message
from core.future_candidates import candidate_probability, choose_candidate, normalize_candidates
from core.action_suggestions import action_suggestion_instruction

log = get_logger()

class BaseResolutionStrategy:
    def resolve(self, session, player_action): raise NotImplementedError

class DualTrackResolver(BaseResolutionStrategy):
    def resolve(self, session, player_action):
        pts = load_system_prompts()
        ctx = session.get_context_text()
        dyn_state = session.get_dynamic_state_for_ai()
        active_world, triggered = session.build_active_world_info(player_action) 
        
        # 1. 变数发散
        react_p = pts.get('reaction_prompt', '').replace('{world_info}', active_world).replace('{character_info}', session.char_info)
        usr_p1 = f"【情景】：\n{ctx}\n【状态】：{json.dumps(dyn_state, ensure_ascii=False)}\n【行动】：{player_action}"
        
        log.info(f"发送推演请求: {player_action[:15]}...")
        raw_react, err1 = session.ai_engine.chat_json(react_p, usr_p1, temp=0.7, trace_label="变数推演")
        reaction_payload = {}
        
        if err1:
            return {"error": True, "stage": "reaction", "message": failure_message(err1)}
        if not raw_react:
            return {"error": True, "stage": "reaction", "message": failure_message(empty=True)}
        else:
            try:
                reaction_payload = robust_json_parse(raw_react)
                raw_candidates = reaction_payload.get('reactions', [])
            except Exception:
                return {"error": True, "stage": "reaction", "message": failure_message(invalid=True)}
        reactions = normalize_candidates(raw_candidates)

        triggered_influences = session.undercurrent.causal_ledger.evaluate_checks(
            reaction_payload.get("influence_checks", [])
        )
        for check in reaction_payload.get("influence_checks", []):
            if isinstance(check, dict):
                log.info(
                    "暗流条件判断: id=%s matched=%s reason=%s",
                    check.get("id", ""), bool(check.get("condition_met", False)), check.get("reason", "")
                )
        for influence in triggered_influences:
            log.info("暗流影响进入正文: id=%s reason=%s", influence["id"], influence["reason"])
        
        for candidate in reactions:
            log.info(
                "动态未来候选: id=%s eligible=%s weight=%s basis=%s description=%s",
                candidate["id"], candidate["eligible"], candidate["weight"], candidate["basis"], candidate["description"],
            )
        chosen = choose_candidate(reactions)
        log.info(
            "物理掷骰选中: id=%s relative_weight=%s normalized_probability=%.4f description=%s",
            chosen["id"], chosen["weight"], candidate_probability(chosen, reactions), chosen["description"],
        )
        
        # 2. 剧情结算
        visible_world, _ = session.build_visible_world_info(player_action)
        settle_p = pts.get('settlement_prompt', '').replace('{world_info}', visible_world).replace('{character_info}', session.char_info).replace('{style_info}', session.style_info).replace('{word_limit}', str(session.word_limit))
        suggestion_prompt = action_suggestion_instruction(session.story_settings.get("aiSuggestions", True))
        if suggestion_prompt:
            settle_p += "\n\n【玩家行动建议要求】\n" + suggestion_prompt
        influence_instruction = "（本回合没有满足条件的暗流影响）"
        if triggered_influences:
            influence_instruction = "\n".join(
                f"- [{item['id']}] {item['summary']}；必须体现的后果：{item['effect']}；依据：{item['reason']}"
                for item in triggered_influences
            )
        usr_p2 = f"{usr_p1}\n【裁定变数】：{chosen['description']}\n【本回合必须兑现的暗流影响】：\n{influence_instruction}"
        
        raw_settle, err2 = session.ai_engine.chat_json(settle_p, usr_p2, temp=0.8, max_tokens=max(3000, int(session.word_limit*3)), trace_label="剧情结算")
        
        if err2:
            return {"error": True, "stage": "settlement", "message": failure_message(err2)}
        if not raw_settle:
            return {"error": True, "stage": "settlement", "message": failure_message(empty=True)}
        else:
            try: settlement = robust_json_parse(raw_settle)
            except Exception: return {"error": True, "stage": "settlement", "message": failure_message(invalid=True)}

        triggered_ids = {item["id"] for item in triggered_influences}
        reported = []
        reported_ids = set()
        for item in settlement.get("resolved_influences", []):
            if not isinstance(item, dict):
                continue
            influence_id = str(item.get("id", ""))
            if influence_id not in triggered_ids:
                log.warning("忽略正文越权报告的暗流影响: %s", influence_id or "空ID")
                continue
            if influence_id in reported_ids:
                continue
            reported.append(item)
            reported_ids.add(influence_id)
        for influence in triggered_influences:
            if influence["id"] not in reported_ids:
                log.warning("正文未报告强制暗流影响的结构化结果: %s", influence["id"])
                reported.append({"id": influence["id"], "result": "已按条件触发结算；正文未返回结构化结果"})
        settlement["resolved_influences"] = reported

        return {
            "reactions": reactions, "chosen_reaction": chosen,
            "settlement": settlement, "triggered_entries": triggered,
            "triggered_influences": triggered_influences,
        }
