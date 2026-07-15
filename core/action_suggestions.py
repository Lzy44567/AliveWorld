"""Player-visible next-action suggestions returned with story settlement."""

from __future__ import annotations

from typing import Any
import re


MAX_SUGGESTIONS = 4
MAX_SUGGESTION_LENGTH = 120


def normalize_action_suggestions(value: Any, *, enabled: bool = True) -> list[str]:
    """Keep a small, stable, player-safe presentation shape.

    Semantic secrecy is enforced by the settlement context boundary and prompt;
    this function handles malformed output, duplicates and UI-sized limits.
    """
    if not enabled or not isinstance(value, list):
        return []
    output: list[str] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, str):
            continue
        item = " ".join(raw.split()).strip()
        if not item:
            continue
        item = item[:MAX_SUGGESTION_LENGTH].rstrip()
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
        if len(output) >= MAX_SUGGESTIONS:
            break
    return output


def action_suggestion_instruction(enabled: bool) -> str:
    if not enabled:
        return ""
    return (
        "根据本轮已经写出的 story_text、玩家可见状态和玩家已知信息，给出 2-4 个实质不同、"
        "可以立刻采取的下一步行动，写入 action_suggestions。建议是玩家行动，不是剧情结果；"
        "不得使用未在正文显露的暗流实体、因果账本、未触发陷阱、后台计划或未被选中的未来候选。"
        "每项使用自然、简短、可直接编辑的第一人称行动描述，不替玩家决定唯一选择。"
    )


def resolve_action_reference(user_action: str, suggestions: list[str]) -> str:
    """Expand inputs such as ``A，再谨慎一点`` against the last suggestions."""
    text = str(user_action or "").strip()
    if not text or not suggestions:
        return text
    exact = re.fullmatch(r"(?:选(?:择)?\s*)?([A-Da-d1-4])", text)
    detailed = re.fullmatch(r"(?:选(?:择)?\s*)?([A-Da-d1-4])(?:\s*[.、:：+＋，,]\s*|\s+)(.+)", text)
    match = detailed or exact
    if not match:
        return text
    token = match.group(1).upper()
    index = int(token) - 1 if token.isdigit() else ord(token) - ord("A")
    if index < 0 or index >= len(suggestions):
        return text
    selected = suggestions[index]
    supplement = match.group(2).strip() if detailed else ""
    if supplement:
        return f"【玩家选择的建议行动】{selected}\n【玩家补充】{supplement}"
    return selected
