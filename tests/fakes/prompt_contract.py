"""Declarative prompt markers used by the isolated fake model service.

Markers deliberately live outside production code.  They let browser tests prove
which context reached which AI task without relying on a real model's wording.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


EXPLICIT_MARKER_RE = re.compile(r"【AWTEST:(?P<name>[^】\r\n]{1,80})】")
STORY_INDEX_RE = re.compile(r"自动测试正文\s*(?P<index>\d+)")


@dataclass(frozen=True)
class PromptMarker:
    name: str
    needle: str
    visible_reply: str = ""


BUILTIN_MARKERS = (
    PromptMarker("worldbook", "测试世界书", "世界书就绪"),
    PromptMarker("character", "测试角色卡", "角色卡就绪"),
    PromptMarker("style", "测试文风", "文风就绪"),
    PromptMarker("entity", "测试实体", "实体上下文就绪"),
    PromptMarker("gm_protocol", "游戏地下城主", "GM 提示词就绪"),
    PromptMarker("status_protocol", '"status_updates"', "状态栏规则就绪"),
    PromptMarker("agency_protocol", "本回合行动事实裁定", "行动裁定就绪"),
)


def scan_prompt(prompt: str) -> list[str]:
    """Return stable marker names in first-seen order."""

    found: list[str] = []
    for marker in BUILTIN_MARKERS:
        if marker.needle in prompt and marker.name not in found:
            found.append(marker.name)
    for match in EXPLICIT_MARKER_RE.finditer(prompt):
        name = match.group("name").strip()
        if name and name not in found:
            found.append(name)
    return found


def visible_readiness_lines(prompt: str) -> list[str]:
    """Human-readable evidence returned by the fake story model."""

    lines = [marker.visible_reply for marker in BUILTIN_MARKERS if marker.visible_reply and marker.needle in prompt]
    lines.extend(f"{match.group('name').strip()}就绪" for match in EXPLICIT_MARKER_RE.finditer(prompt))
    return list(dict.fromkeys(line for line in lines if line))


def next_story_index(prompt: str) -> int:
    """Derive the next fake chapter number from the history actually supplied."""

    indices = [int(match.group("index")) for match in STORY_INDEX_RE.finditer(prompt)]
    return max(indices, default=0) + 1
