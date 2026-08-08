"""Story-length normalization and prompt contract."""

from __future__ import annotations

from typing import Any


DEFAULT_TARGET_STORY_LENGTH = 500
MIN_TARGET_STORY_LENGTH = 200
MAX_TARGET_STORY_LENGTH = 3000


def normalize_target_story_length(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_TARGET_STORY_LENGTH
    return max(MIN_TARGET_STORY_LENGTH, min(MAX_TARGET_STORY_LENGTH, parsed))


def story_length_instruction(value: Any) -> str:
    target = normalize_target_story_length(value)
    tolerance = max(80, round(target * 0.2 / 50) * 50)
    return (
        "【本回合正文篇幅】\n"
        f"目标约 {target} 个中文字符，允许按场景完整性上下浮动约 {tolerance} 字。"
        "不要为凑字数重复描写，也不要在关键动作、对白或因果尚未完成时生硬截断。"
        "该目标只约束 story_text，不包含其他 JSON 结构字段。"
    )
