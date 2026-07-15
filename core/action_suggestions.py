"""Player-visible next-action suggestions returned with story settlement."""

from __future__ import annotations

from typing import Any


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
        return "本局已关闭 AI 行动建议。action_suggestions 必须返回空数组 []。"
    return (
        "根据本轮已经写出的 story_text、玩家可见状态和玩家已知信息，给出 2-4 个实质不同、"
        "可以立刻采取的下一步行动，写入 action_suggestions。建议是玩家行动，不是剧情结果；"
        "不得使用未在正文显露的暗流实体、因果账本、未触发陷阱、后台计划或未被选中的未来候选。"
        "每项使用自然、简短、可直接编辑的第一人称行动描述，不替玩家决定唯一选择。"
    )
