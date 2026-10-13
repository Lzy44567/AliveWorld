"""Small, genre-neutral evidence contract; not permission to edit world assets."""

from typing import Any


EVENT_ENUMS = {
    "fact_status": {"confirmed", "attempted", "reported", "uncertain"},
    "change_kind": {"add", "update", "suspend", "restore", "expire"},
    "scope_hint": {"global", "region", "organization", "group", "location", "individual_exception"},
    "time_hint": {"persistent", "until_condition", "fixed_duration", "uncertain"},
}

SIGNAL_INSTRUCTION = """【世界变化信号】报告本回合首次确认的可复用世界知识（用add，不要求世界刚刚改变），或确认成立的世界规则变化，不依赖命令词或题材。仅随口提名、无机制的招式不捕获；已明确且影响后续行动的技能机制可以记录，谁掌握技能仍归人物。区分事实与尝试、愿望、对白、传闻、梦境、假设；单次剧情结果、伤势和物品位置不属于世界规则。返回 world_change_events 数组，无变化返回 []，不得为了捕获虚构设定。
每项字段：summary（简述变化）、fact_status（confirmed|attempted|reported|uncertain）、change_kind（add|update|suspend|restore|expire）、scope_hint（global|region|organization|group|location|individual_exception）、time_hint（persistent|until_condition|fixed_duration|uncertain）、evidence（从本回合 story_text 逐字摘录的依据）。最多8项。只有 confirmed 且证据确实出现在正文的信号会触发详细捕获；你不直接编辑世界书。"""


def validate_world_change_events(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) > 8:
        raise ValueError("world_change_events 必须是最多8项的数组")
    result = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise ValueError(f"world_change_events[{index}] 必须是对象")
        event = {}
        for field, allowed in EVENT_ENUMS.items():
            if not isinstance(raw.get(field), str) or raw[field] not in allowed:
                raise ValueError(f"world_change_events[{index}].{field} 枚举无效")
            event[field] = raw[field]
        for field, limit in (("summary", 300), ("evidence", 500)):
            text = raw.get(field)
            if not isinstance(text, str) or not text.strip() or len(text) > limit:
                raise ValueError(f"world_change_events[{index}].{field} 必须是非空短文本（最多{limit}字）")
            event[field] = text.strip()
        if event not in result:
            result.append(event)
    return result


def confirmed_world_changes(settlement: Any) -> list[dict[str, str]]:
    if not isinstance(settlement, dict):
        return []
    try:
        events = validate_world_change_events(settlement.get("world_change_events", []))
    except ValueError:
        return []
    story = settlement.get("story_text", "")
    if not isinstance(story, str):
        return []
    return [event for event in events if event["fact_status"] == "confirmed" and event["evidence"] in story]
