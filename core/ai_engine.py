# core/ai_engine.py
import json, re
from openai import OpenAI
from utils.sys_logger import get_logger

log = get_logger()

def intelligent_salvage(raw_str, error_msg):
    log.warning(f"启动智能打捞引擎... 原因: {error_msg}")
    story = raw_str.strip()
    if not story or story.startswith('{'): story = f"*(系统提示：大模型返回了破损残片)*\n\n[残片]：{raw_str[:100]}..."
    return {
        "story_text": story + "\n\n*(🔧 引擎防溃盾：已强制打捞正文，跳过数值更新。)*",
        "numeric_changes": {"hp": 0, "max_hp": 0, "mana": 0, "max_mana": 0},
        "new_buffs": {}, "remove_buffs": [], "dynamic_bars": {},
        "status_updates": {}, "npc_states": {}, "status_deletions": []
    }

def robust_json_parse(raw_str):
    if not raw_str or not str(raw_str).strip(): raise ValueError("空字符串")
    try: return json.loads(raw_str)
    except Exception as e:
        match = re.search(r'```(?:json)?(.*?)```', raw_str, re.DOTALL)
        if match:
            try: return json.loads(match.group(1).strip())
            except: pass
        raise ValueError(f"JSON 解析失败: {e}")

class AIEngine:
    def __init__(self, config):
        self.client = OpenAI(api_key=config['api_key'], base_url=config['base_url'])
        self.model = config['model']

    def chat_json(self, system_prompt, user_prompt, temp=0.8, max_tokens=None):
        """强制 JSON 输出模式（主线 DM 用）"""
        try:
            kwargs = {"model": self.model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": temp, "response_format": {"type": "json_object"}}
            if max_tokens: kwargs["max_tokens"] = max_tokens
            res = self.client.chat.completions.create(**kwargs)
            return res.choices[0].message.content or "", None
        except Exception as e: return "", str(e)

    def chat_text(self, system_prompt, user_prompt, temp=0.8):
        """纯文本输出模式（暗流实体引擎用）"""
        try:
            res = self.client.chat.completions.create(
                model=self.model, 
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], 
                temperature=temp
            )
            return res.choices[0].message.content or "", None
        except Exception as e: return "", str(e)