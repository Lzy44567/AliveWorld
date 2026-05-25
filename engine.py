# engine.py
import json
import re
import random
from openai import OpenAI
from prompts import get_reaction_prompt, get_settlement_prompt, get_style_expansion_prompt, get_world_architect_prompt, get_entry_expansion_prompt
from sys_logger import get_logger

log = get_logger()

def robust_json_parse(raw_str):
    """【超级铁壁】：无论AI怎么乱加文本，强行把 JSON 挖出来"""
    raw_str = raw_str.strip()
    try:
        return json.loads(raw_str)
    except Exception as e:
        log.warning(f"原生解析失败，尝试正则表达式挖掘... 原因: {e}")
        # 尝试 1: 寻找 markdown 代码块
        match = re.search(r'```(?:json)?(.*?)```', raw_str, re.DOTALL)
        if match:
            try: return json.loads(match.group(1).strip())
            except: pass
        # 尝试 2: 寻找最外层大括号 (解决AI在JSON前后废话的问题)
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
            # 同样加上 json_object 约束
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
            # 【修复 1】：强制 response_format
            res = self.client.chat.completions.create(
                model=self.model, 
                messages=[{"role": "system", "content": get_reaction_prompt(character_info, world_info)}, {"role": "user", "content": prompt}], 
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            raw_str = res.choices[0].message.content
            parsed = robust_json_parse(raw_str)
            return parsed.get('reactions', []), raw_str
        except Exception as e: 
            log.error(f"推演提取失败: {e}")
            return None, raw_str if 'raw_str' in locals() else str(e)

    def roll_dice(self, reactions):
        if not reactions: return None
        return random.choices(reactions, weights=[p['weight'] for p in reactions], k=1)[0]

    def generate_story_and_state(self, context, player_action, chosen_reaction, dynamic_state, word_limit, character_info, style_info, world_info):
        prompt = f"【情景】：{context}\n【状态】：{json.dumps(dynamic_state, ensure_ascii=False)}\n【行动】：{player_action}\n【变数】：{chosen_reaction['description']}"
        try:
            # 【修复 2】：强制 response_format 且大幅放宽 max_tokens 限制防止字数截断
            res = self.client.chat.completions.create(
                model=self.model, 
                messages=[{"role": "system", "content": get_settlement_prompt(word_limit, character_info, style_info, world_info)}, {"role": "user", "content": prompt}], 
                temperature=0.8, 
                max_tokens=max(2500, int(word_limit * 3)),
                response_format={"type": "json_object"}
            )
            raw_str = res.choices[0].message.content
            return robust_json_parse(raw_str), raw_str
        except Exception as e: 
            log.error(f"结算提取失败: {e}")
            return None, raw_str if 'raw_str' in locals() else str(e)