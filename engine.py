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
            finish_reason = res.choices[0].finish_reason
            
            # 【终极防线】：处理推演期被审核的情况
            if not raw_str.strip():
                log.warning(f"推演期被拦截，finish_reason: {finish_reason}")
                return [{"id": 1, "description": "系统提示：一阵神秘的法则之力（API安全审查）抹除了这个时空的发展可能性，什么事都没有发生。", "weight": 100}], ""
                
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
            res = self.client.chat.completions.create(
                model=self.model, 
                messages=[{"role": "system", "content": get_settlement_prompt(word_limit, character_info, style_info, world_info)}, {"role": "user", "content": prompt}], 
                temperature=0.8, 
                max_tokens=max(2500, int(word_limit * 3)),
                response_format={"type": "json_object"}
            )
            
            raw_str = res.choices[0].message.content or ""
            finish_reason = res.choices[0].finish_reason
            
            # 【终极防线】：处理结算期被审核的情况
            if not raw_str.strip():
                log.warning(f"结算期被拦截，finish_reason: {finish_reason}")
                fallback_json = {
                    "story_text": "*(系统提示：因为该段剧情触发了大语言模型的 NSFW/暴力 审查拦截，因果律被强制切断。)*\n这股强大的外来法则之力让你们双方都愣住了，战斗出现了短暂的停滞...",
                    "numeric_changes": {"hp": 0, "max_hp": 0, "mana": 0, "max_mana": 0},
                    "new_buffs": {}, "remove_buffs": [], "dynamic_bars": {},
                    "status_updates": {}, "npc_states": {}, "status_deletions": []
                }
                return fallback_json, "(内容被API拦截，触发空字符返回)"
                
            return robust_json_parse(raw_str), raw_str
        except Exception as e: 
            log.error(f"结算提取失败: {e}")
            return None, raw_str if 'raw_str' in locals() else str(e)