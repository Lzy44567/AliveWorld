# engine.py
import json
import re
import random
from openai import OpenAI
from prompts import get_reaction_prompt, get_settlement_prompt, get_style_expansion_prompt, get_world_architect_prompt, get_entry_expansion_prompt
from sys_logger import get_logger

log = get_logger()

def robust_json_parse(raw_str):
    if not raw_str or not str(raw_str).strip():
        raise ValueError("输入内容为空 (Empty String)。")
    raw_str = str(raw_str).strip()
    try:
        return json.loads(raw_str)
    except Exception as e:
        log.warning(f"原生解析失败，尝试正则表达式挖掘... 原因: {e}")
        match = re.search(r'```(?:json)?(.*?)```', raw_str, re.DOTALL)
        if match:
            try: return json.loads(match.group(1).strip())
            except: pass
        match = re.search(r'\{.*\}', raw_str, re.DOTALL)
        if match:
            try: return json.loads(match.group(0).strip())
            except: pass
        
        log.error("JSON 挖掘彻底失败！请检查AI输出的文本！")
        raise ValueError("无法从大模型输出中解析出合法的 JSON 字典。")

class AIEngine:
    def __init__(self, config):
        self.client = OpenAI(api_key=config['api_key'], base_url=config['base_url'])
        self.model = config['model']

    def expand_style(self, short_desc):
        try:
            return self.client.chat.completions.create(model=self.model, messages=[{"role": "system", "content": get_style_expansion_prompt()}, {"role": "user", "content": short_desc}], temperature=0.8).choices[0].message.content
        except Exception as e: return f"生成失败: {e}"

    def generate_worldbook(self, inspiration):
        try:
            res = self.client.chat.completions.create(model=self.model, messages=[{"role": "system", "content": get_world_architect_prompt()}, {"role": "user", "content": f"世界灵感：{inspiration}"}], temperature=0.8, response_format={"type": "json_object"})
            return robust_json_parse(res.choices[0].message.content)
        except Exception as e: log.error(f"世界生成失败: {e}"); return None

    def expand_world_entry(self, entry_idea):
        try:
            return self.client.chat.completions.create(model=self.model, messages=[{"role": "system", "content": get_entry_expansion_prompt()}, {"role": "user", "content": f"词条灵感：{entry_idea}"}], temperature=0.8).choices[0].message.content
        except Exception as e: return f"词条扩写失败: {e}"

    def get_world_reactions(self, context, player_action, dynamic_state, character_info, world_info):
        prompt = f"【情景】：\n{context}\n【状态】：{json.dumps(dynamic_state, ensure_ascii=False)}\n【玩家行动】：{player_action}"
        try:
            res = self.client.chat.completions.create(
                model=self.model, 
                messages=[{"role": "system", "content": get_reaction_prompt(character_info, world_info)}, {"role": "user", "content": prompt}], 
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            raw_str = res.choices[0].message.content or ""
            return robust_json_parse(raw_str).get('reactions', []), raw_str
        except Exception as e: 
            # 【终极防线 1：遭遇 API 异常或截断时的完美兜底】
            log.error(f"推演提取彻底拦截: {e}")
            return [{"id": 1, "description": f"系统提示：一股强大的外来法则之力（API安全审查或模型崩溃）阻挡了命运的推演。原因：{e}", "weight": 100}], ""

    def roll_dice(self, reactions):
        if not reactions: return None
        return random.choices(reactions, weights=[p['weight'] for p in reactions], k=1)[0]

    def generate_story_and_state(self, context, player_action, chosen_reaction, dynamic_state, word_limit, character_info, style_info, world_info):
        prompt = f"【情景】：{context}\n【状态】：{json.dumps(dynamic_state, ensure_ascii=False)}\n【行动】：{player_action}\n【变数】：{chosen_reaction['description']}"
        try:
            res = self.client.chat.completions.create(
                model=self.model, 
                messages=[{"role": "system", "content": get_settlement_prompt(word_limit, character_info, style_info, world_info)}, {"role": "user", "content": prompt}], 
                temperature=0.8, 
                max_tokens=max(2500, int(word_limit * 3)),
                response_format={"type": "json_object"}
            )
            raw_str = res.choices[0].message.content or ""
            return robust_json_parse(raw_str), raw_str
        except Exception as e: 
            # 【终极防线 2：安全接管主界面输出】
            log.error(f"结算提取彻底拦截: {e}")
            fallback_json = {
                "story_text": f"*(系统警报：这段剧情触犯了世界的底层法则（通常为大模型 API 屏蔽了敏感内容），因果律被强制切断。)*\n\n这股强大的力量让时间停滞了一瞬，请尝试改变你的行动，或点击下方的【一键重推】按钮。",
                "numeric_changes": {"hp": 0, "max_hp": 0, "mana": 0, "max_mana": 0},
                "new_buffs": {}, "remove_buffs": [], "dynamic_bars": {},
                "status_updates": {}, "npc_states": {}, "status_deletions": []
            }
            return fallback_json, f"(拦截兜底触发) {e}"