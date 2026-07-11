"""Local audit trail for model-bound prompts and their results.

The trace deliberately receives prompts and model metadata only. API keys and
other connection credentials never enter this module.
"""

from uuid import uuid4

from utils.sys_logger import get_logger


log = get_logger()


def begin_llm_trace(label, model, system_prompt, user_prompt, response_mode):
    trace_id = uuid4().hex[:8]
    log.info(
        "LLM 请求 [%s] id=%s model=%s mode=%s\n[SYSTEM]\n%s\n[USER]\n%s",
        label or "unspecified",
        trace_id,
        model,
        response_mode,
        system_prompt,
        user_prompt,
    )
    return trace_id


def finish_llm_trace(label, trace_id, response="", error=None):
    if error:
        log.error("LLM 响应 [%s] id=%s error=%s", label or "unspecified", trace_id, error)
        return
    log.info("LLM 响应 [%s] id=%s\n%s", label or "unspecified", trace_id, response)
