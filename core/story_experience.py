"""Finite built-in story experience presets.

Presets may shape pacing and variety, but they cannot replace engine rules or
the response contract.  The first version intentionally has no user-authored
prompt import surface.
"""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_STORY_EXPERIENCE = "aliveworld_default"
ENGINE_ONLY_EXPERIENCE = "engine_only"


@dataclass(frozen=True)
class StoryExperiencePreset:
    id: str
    title: str
    description: str
    instruction: str


PRESETS: tuple[StoryExperiencePreset, ...] = (
    StoryExperiencePreset(
        DEFAULT_STORY_EXPERIENCE,
        "AliveWorld 默认叙事体验",
        "在不改变规则与结果契约的前提下，减少重复阻碍和强制收束。",
        """【AliveWorld 默认叙事体验】
1. 保持发展路径的实质差异，不要让不同候选反复收束到同一种阻碍、参与者或结局。
2. 戏剧冲突必须由当前已经建立的事实、人物与条件自然产生；日常、封闭或低冲突场景允许自然延续，不为制造刺激强行升级。
3. 同类阻力近期已经反复出现时，优先发展尚未展开的关系、环境反馈或既有线索。""",
    ),
    StoryExperiencePreset(
        ENGINE_ONLY_EXPERIENCE,
        "仅引擎规则",
        "不加载额外叙事体验预设；玩家行动权、因果连续性和 JSON 契约仍然生效。",
        "",
    ),
)

PRESET_BY_ID = {item.id: item for item in PRESETS}


def normalize_story_experience(value: object) -> str:
    preset_id = str(value or "").strip()
    return preset_id if preset_id in PRESET_BY_ID else DEFAULT_STORY_EXPERIENCE


def story_experience_instruction(preset_id: object) -> str:
    return PRESET_BY_ID[normalize_story_experience(preset_id)].instruction


def story_experience_options() -> list[dict[str, str]]:
    return [
        {"value": item.id, "label": item.title, "description": item.description}
        for item in PRESETS
    ]
