# core/resolution_engine.py
import random
import json
from utils.sys_logger import get_logger
from core.prompts import load_system_prompts
from core.ai_engine import robust_json_parse, intelligent_salvage

log = get_logger()

class BaseResolutionStrategy:
    """推演策略基类，未来你可以实现 N*n 贝叶斯推演策略继承此类"""
    def resolve(self, session, player_action): raise NotImplementedError

class DualTrackResolver(BaseResolutionStrategy):
    """当前正在使用的：双轨掷骰推演"""
    def resolve(self, session, player_action):
        pts = load_system_prompts()
        ctx = session.get_context_text()
        dyn_state = session.get_dynamic_state_for_ai()
        active_world = session.build_active_world_info(player_action)
        
        # 1. 第一轨：生成变数
        react_p = pts.get('reaction_prompt', '').replace('{world_info}', active_world).replace('{character_info}', session.char_info)
        usr_p1 = f"【情景】：\n{ctx}\n【状态】：{json.dumps(dyn_state, ensure_ascii=False)}\n【行动】：{player_action}"
        
        raw_react, err1 = session.ai_engine.chat_json(react_p, usr_p1, temp=0.7)
        if err1 or not raw_react: 
            reactions = [{"id": 1, "description": f"系统提示：法则拦截({err1})", "weight": 100}]
        else:
            try: reactions = robust_json_parse(raw_react).get('reactions', [])
            except: reactions = [{"id": 1, "description": "系统提示：因果混沌", "weight": 100}]
        
        # 2. Python 物理掷骰裁定
        chosen = random.choices(reactions, weights=[p['weight'] for p in reactions], k=1)[0]
        
        # 3. 第二轨：结算与状态刷新
        settle_p = pts.get('settlement_prompt', '').replace('{world_info}', active_world).replace('{character_info}', session.char_info).replace('{style_info}', session.style_info).replace('{word_limit}', str(session.word_limit))
        usr_p2 = f"{usr_p1}\n【裁定变数】：{chosen['description']}"
        
        raw_settle, err2 = session.ai_engine.chat_json(settle_p, usr_p2, temp=0.8, max_tokens=max(3000, int(session.word_limit*3)))
        
        if err2 or not raw_settle:
            settlement = intelligent_salvage("", "网络或审查拦截")
        else:
            try: settlement = robust_json_parse(raw_settle)
            except Exception as e: settlement = intelligent_salvage(raw_settle, str(e))

        return {
            "reactions": reactions,
            "chosen_reaction": chosen,
            "settlement": settlement
        }