# engine.py
import json
import re
import random
from openai import OpenAI
from prompts import get_reaction_prompt, get_settlement_prompt, get_style_expansion_prompt, get_world_architect_prompt, get_entry_expansion_prompt
from sys_logger import get_logger

log = get_logger()

def extract_story_from_broken_json(broken_json):
    """【手术刀】：从被截断的残缺 JSON 中强行挖出 story_text 的值"""
    start_idx = broken_json.find('"story_text"')
    if start_idx == -1: return ""
    colon_idx = broken_json.find(':', start_idx)
    if colon_idx == -1: return ""
    val_start = broken_json.find('"', colon_idx)
    if val_start == -1: return ""
    end_idx = -1
    for i in range(val_start + 1, len(broken_json)):
        if broken_json[i] == '"' and broken_json[i-1] != '\\':
            end_idx = i
            break
    if end_idx != -1: return broken_json[val_start+1 : end_idx]
    else: return broken_json[val_start+1 :] 

def intelligent_salvage(raw_str, error_msg):
    """【智能打捞引擎】：在 AI 幻觉导致格式损毁时，保住剧情正文"""
    log.warning(f"启动智能打捞引擎... 原因: {error_msg}")
    story = raw_str.strip()
    
    # 方案A：AI 像话痨一样把小说写在了 JSON 前面
    if '{' in story:
        pre_text = story.split('{')[0].strip()
        if len(pre_text) > 50: 
            pre_text = re.sub(r'[a-zA-Z_]+\s*$', '', pre_text).strip() 
            story = pre_text
        else:
            # 方案B：AI 的 JSON 被截断了，强行做外科手术抠出文本
            extracted = extract_story_from_broken_json(story)
            if extracted: story = extracted
            
    if not story or story.startswith('{'):
        story = f"*(系统提示：大模型返回了严重破损的乱码，因果律发生波动)*\n\n[乱码残片]：{raw_str[:100]}..."
        
    story = story.replace('\\n', '\n').replace('\\"', '"')
    
    return {
        "story_text": story + "\n\n*(🔧 引擎防溃盾：检测到 AI 格式崩溃或字数截断，已强制打捞剧情正文，跳过本次数值更新。)*",
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
        
        # 绝不在这里写 log.error，将异常默默抛给打捞引擎！
        raise ValueError(f"JSON 解析失败: {e}")

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
            if not raw_str.strip():
                return [{"id": 1, "description": "系统提示：API安全审查抹除了该时空的发展可能性。", "weight": 100}], ""
            return robust_json_parse(raw_str).get('reactions', []), raw_str
        except Exception as e: 
            log.error(f"推演期彻底崩溃: {e}")
            return [{"id": 1, "description": f"系统提示：一股强大的外来法则之力（模型异常）阻挡了推演。原因：{e}", "weight": 100}], ""

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
                max_tokens=max(3000, int(word_limit * 3)), 
                response_format={"type": "json_object"}
            )
            raw_str = res.choices[0].message.content or ""
            
            if not raw_str.strip():
                log.warning("触发 API 静默审查拦截")
                fallback = intelligent_salvage("*(系统警报：剧情触碰禁忌法则(API审核拦截)，因果律被切断。)*", "拦截空串")
                return fallback, "Empty String"
                
            try:
                # 尝试正常解析
                parsed = robust_json_parse(raw_str)
                return parsed, raw_str
            except Exception as parse_error:
                # 🚨 真正起作用的触发点！
                salvaged = intelligent_salvage(raw_str, parse_error)
                return salvaged, raw_str
                
        except Exception as api_e: 
            log.error(f"结算网络层拦截: {api_e}")
            fallback = intelligent_salvage(f"*(系统警报：网络断开或引擎报错。错误：{api_e})*", "网络异常")
            return fallback, str(api_e)