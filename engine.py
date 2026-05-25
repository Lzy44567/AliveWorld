# engine.py
import json
import random
import logging
from openai import OpenAI
from prompts import get_reaction_prompt, get_settlement_prompt, get_style_expansion_prompt, get_world_architect_prompt, get_entry_expansion_prompt

class AIEngine:
    def __init__(self, config):
        self.client = OpenAI(api_key=config['api_key'], base_url=config['base_url'])
        self.model = config['model']

    def expand_style(self, short_desc):
        sys_prompt = get_style_expansion_prompt()
        try:
            res = self.client.chat.completions.create(
                model=self.model, messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": short_desc}],
                temperature=0.8
            )
            return res.choices[0].message.content
        except Exception as e:
            return f"文风生成失败: {e}"

    def generate_worldbook(self, inspiration):
        sys_prompt = get_world_architect_prompt()
        logging.info(f"========== 架构师正在生成世界: {inspiration} ==========")
        try:
            res = self.client.chat.completions.create(
                model=self.model, 
                messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": f"世界灵感：{inspiration}"}],
                temperature=0.8,
                response_format={"type": "json_object"}
            )
            return json.loads(res.choices[0].message.content)
        except Exception as e:
            logging.error(f"世界书生成失败: {e}")
            return None

    def expand_world_entry(self, entry_idea):
        sys_prompt = get_entry_expansion_prompt()
        try:
            res = self.client.chat.completions.create(
                model=self.model, 
                messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": f"词条灵感：{entry_idea}"}],
                temperature=0.8
            )
            return res.choices[0].message.content
        except Exception as e:
            return f"词条扩写失败: {e}"

    def get_world_reactions(self, context, player_action, dynamic_state, character_info, world_info):
        sys_prompt = get_reaction_prompt(character_info, world_info)
        prompt = f"【情景】：\n{context}\n【状态】：{json.dumps(dynamic_state, ensure_ascii=False)}\n【玩家行动】：{player_action}"
        logging.info("========== 推演阶段 ==========")
        try:
            res = self.client.chat.completions.create(model=self.model, messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}], temperature=0.7, response_format={"type": "json_object"})
            return json.loads(res.choices[0].message.content)['reactions']
        except Exception as e:
            logging.error(f"推演失败: {e}"); return None

    def roll_dice(self, reactions):
        if not reactions: return None
        return random.choices(reactions, weights=[p['weight'] for p in reactions], k=1)[0]

    def generate_story_and_state(self, context, player_action, chosen_reaction, dynamic_state, word_limit, character_info, style_info, world_info):
        sys_prompt = get_settlement_prompt(word_limit, character_info, style_info, world_info)
        prompt = f"【情景】：{context}\n【状态】：{json.dumps(dynamic_state, ensure_ascii=False)}\n【行动】：{player_action}\n【变数】：{chosen_reaction['description']}"
        logging.info("========== 结算阶段 ==========")
        try:
            res = self.client.chat.completions.create(model=self.model, messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}], temperature=0.8, max_tokens=max(800, int(word_limit * 2)), response_format={"type": "json_object"})
            return json.loads(res.choices[0].message.content)
        except Exception as e:
            logging.error(f"生成失败: {e}"); return None