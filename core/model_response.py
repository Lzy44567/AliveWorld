"""Model response validation and player-facing transport errors."""

import re


def failure_message(error=None, *, empty=False, invalid=False):
    text = str(error or "").lower()
    if empty:
        return "模型返回内容为空，请稍后重试。本回合未保存。"
    if invalid:
        return "模型返回格式不完整，无法安全结算。本回合未保存。"
    if "content_filter" in text:
        return "模型服务商过滤了本次输出，请调整内容后重试。本回合未保存。"
    if "length:" in text:
        return "模型输出或上下文达到长度限制，请缩短输入或调整模型上限后重试。本回合未保存。"
    if "insufficient_system_resource" in text:
        return "模型服务商当前推理资源不足，请稍后重试。本回合未保存。"
    if "empty_response" in text:
        return "模型服务商连续返回空白内容，请稍后重试。本回合未保存。"
    if "timeout" in text or "timed out" in text:
        return "模型连接超时，请检查网络、代理/VPN 或 API 服务状态后重试。本回合未保存。"
    return "模型连接失败，请检查网络、代理/VPN、DNS 或 API 服务状态后重试。本回合未保存。"


def format_story_text(value):
    """Honor model breaks; add conservative paragraph breaks to long one-block prose."""
    text = str(value or "").replace("\\n", "\n").strip()
    if not text or "\n\n" in text or len(text) < 220:
        return text
    sentences = [part.strip() for part in re.split(r"(?<=[。！？!?])", text) if part.strip()]
    if len(sentences) < 3:
        return text
    paragraphs, current = [], ""
    target = max(140, min(260, len(text) // 3))
    for sentence in sentences:
        current += sentence
        if len(current) >= target and len(paragraphs) < 3:
            paragraphs.append(current.strip())
            current = ""
    if current:
        paragraphs.append(current.strip())
    return "\n\n".join(paragraphs)
