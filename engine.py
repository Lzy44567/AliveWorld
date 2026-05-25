# engine.py
import json
import re
import random
from openai import OpenAI
from prompts import get_reaction_prompt, get_settlement_prompt, get_style_expansion_prompt, get_world_architect_prompt, get_entry_expansion_prompt
from sys_logger import get_logger

log = get_logger()

def intelligent_salvage(raw_str, error_msg):
    """【智能打捞引擎】：在 AI 幻觉导致 JSON 彻底损毁或截断时，强行挖出小说正文"""
    log.warning(f"启动智能打捞引擎... 原因: {error_msg}")
    story = raw_str.strip()
    
    # 场景1：AI 在 ```json 块前面写了一大堆废话/小说
    if '```json' in story:
        pre_text = story.split('```json')[0].strip()
        if len(pre_text) > 30: # 只要前面的字数够长，就认定那是小说正文
            story = pre_text
    # 场景2：AI 在大括号 { 前面写了小说
    elif '{' in story:
        pre_text = story.split('{')[0].strip()
        if len(pre_text) > 30:
            story = pre_text
    
    # 场景3：如果都没命中，那 AI 可能连 JSON 的边都没沾，就把原始文本全部当做故事
    if not story:
        story = "*(系统提示：大模型返回了无法解析的乱码，因果律发生波动)*"
        
    return {
        "story_text": story + "\n\n*(🔧 引擎提示：检测到模型格式崩溃/字数截断，已自动打捞剧情正文，本次状态变动跳过。)*",
        "numeric_changes": {"hp": 0, "max_hp": 0, "mana": 0, "max_mana": 0},
        "new_buffs": {}, "remove_buffs": [], "dynamic_bars": {},
        "status_updates": {}, "npc_states": {}, "status_deletions": []
    }

def robust_json_parse(raw_str):
    if not raw_str or not str(raw_str).strip():
        raise ValueError("输入内容为空 (Empty String)。")
    raw_str = str(raw_str).strip()
    try:
        return json.loads(raw_str)
    except Exception as e:
        match = re.search(r'```(?:json)?(.*?)```', raw_str, re.DOTALL)
        if match:
            try: return json.loads(match.group(1).strip())
            except: pass
        match = re.search(r'\{.*\}', raw_str, re.DOTALL)
        if match:
            try: return json.loads(match.group(0).strip())
            except: pass
        
        # 不要在这里直接 log.error 吓人，因为我们外层有打捞引擎接管
        raise ValueError(f"JSON解析失败: {e}")

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
            
            # 【核心修复】：尝试正常解析 JSON
            try:
                parsed = robust_json_parse(raw_str)
                return parsed, raw_str
            except Exception as parse_error:
                # 触发智能打捞！抢救小说文本
                salvaged_json = intelligent_salvage(raw_str, parse_error)
                return salvaged_json, raw_str
                
        except Exception as api_e: 
            log.error(f"API网络层拦截: {api_e}")
            fallback_json = {
                "story_text": f"*(系统警报：这段剧情触犯了世界底层法则或网络断开，因果律被强制切断。)*\n\n这股强大的力量让时间停滞了一瞬，请尝试【一键重试】。",
                "numeric_changes": {"hp": 0, "max_hp": 0, "mana": 0, "max_mana": 0},
                "new_buffs": {}, "remove_buffs": [], "dynamic_bars": {},
                "status_updates": {}, "npc_states": {}, "status_deletions": []
            }
            return fallback_json, f"(拦截兜底触发) {api_e}"