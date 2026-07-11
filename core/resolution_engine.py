# core/resolution_engine.py
import random
import json
from utils.sys_logger import get_logger
from core.prompts import load_system_prompts
from core.ai_engine import robust_json_parse, intelligent_salvage

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
        
        if err1 or not raw_react: reactions = [{"id": 1, "description": f"系统提示：法则拦截({err1})", "weight": 100}]
        else:
            try:
                reaction_payload = robust_json_parse(raw_react)
                reactions = reaction_payload.get('reactions', [])
            except: reactions = [{"id": 1, "description": "系统提示：因果混沌", "weight": 100}]
        if not reactions:
            reactions = [{"id": 1, "description": "世界按当前因果继续发展", "weight": 100}]

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
        
        chosen = random.choices(reactions, weights=[p['weight'] for p in reactions], k=1)[0]
        log.info(f"物理掷骰选中: {chosen['description']}")
        
        # 2. 剧情结算
        settle_p = pts.get('settlement_prompt', '').replace('{world_info}', active_world).replace('{character_info}', session.char_info).replace('{style_info}', session.style_info).replace('{word_limit}', str(session.word_limit))
        influence_instruction = "（本回合没有满足条件的暗流影响）"
        if triggered_influences:
            influence_instruction = "\n".join(
                f"- [{item['id']}] {item['summary']}；必须体现的后果：{item['effect']}；依据：{item['reason']}"
                for item in triggered_influences
            )
        usr_p2 = f"{usr_p1}\n【裁定变数】：{chosen['description']}\n【本回合必须兑现的暗流影响】：\n{influence_instruction}"
        
        raw_settle, err2 = session.ai_engine.chat_json(settle_p, usr_p2, temp=0.8, max_tokens=max(3000, int(session.word_limit*3)), trace_label="剧情结算")
        
        if err2 or not raw_settle: settlement = intelligent_salvage("", "网络或审查拦截")
        else:
            try: settlement = robust_json_parse(raw_settle)
            except Exception as e: settlement = intelligent_salvage(raw_settle, str(e))

        reported = settlement.get("resolved_influences", [])
        reported_ids = {item.get("id") for item in reported if isinstance(item, dict)}
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
