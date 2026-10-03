# core/ai_engine.py
import json, re
import time
from core.request_budget import budget_report, require_budget, normalize_usage
from openai import OpenAI
from utils.sys_logger import get_logger
from core.llm_trace import begin_llm_trace, finish_llm_trace
from core.json_stream import JSONTextPreview, STORY_FIELDS

log = get_logger()
STREAM_MAX_BYTES = 128 * 1024
STREAM_MAX_CHUNKS = 4096


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
        "normalizedUsage": normalize_usage(usage),
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
        self.budget_options = dict(config.get('budget_options') or {})

    def chat_json(self, system_prompt, user_prompt, temp=0.8, max_tokens=None, trace_label="json", prompt_manifest=None, *, on_text_delta=None, visible_fields=None):
        """强制 JSON 输出模式（主线 DM 用）"""
        trace_id = begin_llm_trace(trace_label, self.model, system_prompt, user_prompt, "json", prompt_manifest)
        started = time.monotonic()
        report = {}
        try:
            report = budget_report(system_prompt, user_prompt, max_tokens, self.budget_options, prompt_manifest)
            require_budget(report)
            kwargs = {"model": self.model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": temp, "response_format": {"type": "json_object"}}
            kwargs["max_tokens"] = report["outputReserve"]
            if on_text_delta is not None:
                return self._stream_json(kwargs, on_text_delta, visible_fields or STORY_FIELDS,
                                         trace_label, trace_id, report, started)
            for attempt in (1, 2):
                report = budget_report(system_prompt, kwargs["messages"][-1]["content"], kwargs["max_tokens"], self.budget_options, prompt_manifest)
                require_budget(report)
                res = self.client.chat.completions.create(**kwargs)
                content = res.choices[0].message.content or ""
                metadata = _completion_metadata(res, attempt)
                metadata.update(budget=report, elapsedMs=round((time.monotonic() - started) * 1000))
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
            finish_llm_trace(trace_label, trace_id, error=str(e), metadata={"budget": report})
            return "", str(e)

    def _stream_json(self, kwargs, emit, fields, label, trace_id, report, started):
        """One real provider stream; never retry or fall back to another paid call."""
        preview = JSONTextPreview(fields, emit)
        parts, usage, response_id, finish_reason = [], None, "", ""
        stream = None
        size = 0
        try:
            # OpenAI SDK defaults to retries; opt out specifically for this attempt.
            client = self.client.with_options(max_retries=0, timeout=120.0)
            stream = client.chat.completions.create(**kwargs, stream=True)
            for chunk_count, chunk in enumerate(stream, 1):
                if chunk_count > STREAM_MAX_CHUNKS:
                    raise ValueError("stream_chunk_limit: 模型流超出安全分片上限")
                response_id = str(getattr(chunk, "id", "") or response_id)
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage is not None:
                    usage = chunk_usage.model_dump() if hasattr(chunk_usage, "model_dump") else chunk_usage
                for choice in getattr(chunk, "choices", []):
                    if getattr(choice, "index", 0) != 0:
                        continue
                    reason = getattr(choice, "finish_reason", None)
                    if reason:
                        finish_reason = str(reason)
                        if finish_reason != "stop":
                            raise ValueError(_empty_response_error({"finish_reason": finish_reason}))
                    # Never consume reasoning_content, tool_calls or any other delta.
                    delta = getattr(choice, "delta", None)
                    if getattr(delta, "tool_calls", None) or getattr(delta, "function_call", None):
                        raise ValueError("stream_tools_unsupported: JSON生成不允许工具调用")
                    content = getattr(delta, "content", None)
                    if not content:
                        continue
                    if not isinstance(content, str):
                        raise ValueError("Invalid streamed content type")
                    size += len(content.encode("utf-8"))
                    if size > STREAM_MAX_BYTES:
                        raise ValueError("stream_output_limit: 模型输出超出安全上限")
                    parts.append(content)
                    preview.feed(content)
            metadata = {
                "response_id": response_id, "finish_reason": finish_reason, "attempt": 1,
                "usage": usage or {}, "normalizedUsage": normalize_usage(usage),
                "budget": report, "elapsedMs": round((time.monotonic() - started) * 1000),
            }
            raw = "".join(parts)
            if finish_reason != "stop":
                error = _empty_response_error(metadata) if finish_reason else "incomplete_stream: 模型流未完整结束"
                finish_llm_trace(label, trace_id, error=error, metadata=metadata)
                return "", error
            if not raw.strip():
                error = _empty_response_error(metadata)
                finish_llm_trace(label, trace_id, error=error, metadata=metadata)
                return "", error
            # Preview is not validation. In particular, trailing partial JSON fails.
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("Streaming model must return a JSON object")
            finish_llm_trace(label, trace_id, response=raw, metadata=metadata)
            return raw, None
        finally:
            if stream is not None:
                stream.close()

    def chat_text(self, system_prompt, user_prompt, temp=0.8, trace_label="text", prompt_manifest=None):
        """纯文本输出模式（暗流实体引擎用）"""
        trace_id = begin_llm_trace(trace_label, self.model, system_prompt, user_prompt, "text", prompt_manifest)
        started = time.monotonic()
        report = {}
        try:
            report = budget_report(system_prompt, user_prompt, options=self.budget_options, manifest=prompt_manifest)
            require_budget(report)
            res = self.client.chat.completions.create(
                model=self.model, 
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], 
                temperature=temp, max_tokens=report["outputReserve"]
            )
            content = res.choices[0].message.content or ""
            metadata = _completion_metadata(res)
            metadata.update(budget=report, elapsedMs=round((time.monotonic() - started) * 1000))
            if not content.strip():
                error = _empty_response_error(metadata)
                finish_llm_trace(trace_label, trace_id, error=error, metadata=metadata)
                return "", error
            finish_llm_trace(trace_label, trace_id, response=content, metadata=metadata)
            return content, None
        except Exception as e:
            finish_llm_trace(trace_label, trace_id, error=str(e), metadata={"budget": report})
            return "", str(e)
