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


def normalize_minimum_story_length(value: Any, maximum: Any) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        parsed = 0
    return max(0, min(normalize_target_story_length(maximum), parsed))


def story_length_instruction(value: Any, minimum: Any = 0) -> str:
    target = normalize_target_story_length(value)
    lower = normalize_minimum_story_length(minimum, target)
    guidance = (f"建议正文为 {lower}–{target} 个中文字符。" if lower
                else f"目标约 {target} 个中文字符以内，不要求最低长度。")
    return (
        "【本回合正文篇幅】\n"
        + guidance + "这是软建议，场景完整性优先，允许合理超出范围。"
        "不要为凑字数重复描写，也不要在关键动作、对白或因果尚未完成时生硬截断。"
        "该目标只约束 story_text，不包含其他 JSON 结构字段。"
    )
