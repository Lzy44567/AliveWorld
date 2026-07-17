# core/ai_engine.py
import json, re
from openai import OpenAI
from utils.sys_logger import get_logger
from core.llm_trace import begin_llm_trace, finish_llm_trace

log = get_logger()


def _completion_metadata(response, attempt=1):
    choice = response.choices[0]
    usage = getattr(response, "usage", None)
    if hasattr(usage, "model_dump"):
        usage = usage.model_dump()
    elif usage is not None and not isinstance(usage, dict):
        usage = {
            key: getattr(usage, key)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            if getattr(usage, key, None) is not None
        }
    return {
        "response_id": str(getattr(response, "id", "") or ""),
        "finish_reason": str(getattr(choice, "finish_reason", "") or ""),
        "attempt": attempt,
        "usage": usage or {},
    }


def _empty_response_error(metadata):
    reason = metadata.get("finish_reason", "")
    if reason == "content_filter":
        return "content_filter: 模型服务商过滤了本次输出"
    if reason == "length":
        return "length: 模型达到输出或上下文长度限制，未返回有效内容"
    if reason == "insufficient_system_resource":
        return "insufficient_system_resource: 模型服务商推理资源不足"
    return f"empty_response: 模型服务商返回空白内容（finish_reason={reason or 'unknown'}）"

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

    def chat_json(self, system_prompt, user_prompt, temp=0.8, max_tokens=None, trace_label="json"):
        """强制 JSON 输出模式（主线 DM 用）"""
        trace_id = begin_llm_trace(trace_label, self.model, system_prompt, user_prompt, "json")
        try:
            kwargs = {"model": self.model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": temp, "response_format": {"type": "json_object"}}
            if max_tokens: kwargs["max_tokens"] = max_tokens
            for attempt in (1, 2):
                res = self.client.chat.completions.create(**kwargs)
                content = res.choices[0].message.content or ""
                metadata = _completion_metadata(res, attempt)
                if content.strip():
                    finish_llm_trace(trace_label, trace_id, response=content, metadata=metadata)
                    return content, None
                error = _empty_response_error(metadata)
                if metadata["finish_reason"] == "content_filter" or attempt == 2:
                    finish_llm_trace(trace_label, trace_id, error=error, metadata=metadata)
                    return "", error
                log.warning(
                    "LLM JSON 空白响应，执行一次受控重试: label=%s id=%s finish_reason=%s",
                    trace_label, trace_id, metadata["finish_reason"] or "unknown",
                )
                kwargs["messages"] = [*kwargs["messages"][:-1], {
                    "role": "user",
                    "content": user_prompt + "\n\n请立即只返回一个完整 JSON 对象，禁止只输出空白字符。",
                }]
        except Exception as e:
            finish_llm_trace(trace_label, trace_id, error=str(e))
            return "", str(e)

    def chat_text(self, system_prompt, user_prompt, temp=0.8, trace_label="text"):
        """纯文本输出模式（暗流实体引擎用）"""
        trace_id = begin_llm_trace(trace_label, self.model, system_prompt, user_prompt, "text")
        try:
            res = self.client.chat.completions.create(
                model=self.model, 
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], 
                temperature=temp
            )
            content = res.choices[0].message.content or ""
            metadata = _completion_metadata(res)
            if not content.strip():
                error = _empty_response_error(metadata)
                finish_llm_trace(trace_label, trace_id, error=error, metadata=metadata)
                return "", error
            finish_llm_trace(trace_label, trace_id, response=content, metadata=metadata)
            return content, None
        except Exception as e:
            finish_llm_trace(trace_label, trace_id, error=str(e))
            return "", str(e)
