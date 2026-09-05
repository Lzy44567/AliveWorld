"""Detect optional player-facing world-rule commands without taxing normal prompts."""

from __future__ import annotations

import re
from typing import Any


RULE_CHANGE = re.compile(r"(?:^|[\n。！？（(])\s*常识改变\s*[：:]", re.IGNORECASE)
RULE_RESTORE = re.compile(r"(?:^|[\n。！？（(])\s*常识(?:恢复|复原)(?:\s*[：:].*)?(?:$|[\n。！？）)])", re.IGNORECASE)


def world_rule_command_mode(player_action: Any) -> str:
    """Return an explicit command adapter mode, never a genre/topic guess."""
    text = str(player_action or "").strip()
    if RULE_RESTORE.search(text):
        return "restore"
    if RULE_CHANGE.search(text):
        return "change"
    return ""


def resolution_instruction(player_action: Any) -> str:
    """Small per-turn instruction; an ordinary turn adds exactly zero prompt text."""
    mode = world_rule_command_mode(player_action)
    if mode == "change":
        return (
            "【本回合显式世界规则变更意图】玩家要求改变一项长期世界规则。"
            "这不是自动成功许可；请依据既有设定和玩家权限裁定。若正文确认规则已生效，"
            "必须令 worldbook_capture_needed 为 true；失败或仅表达愿望时为 false。"
        )
    if mode == "restore":
        return (
            "【本回合显式世界规则恢复意图】玩家要求恢复一项先前被改变的长期世界规则。"
            "这不是自动成功许可；请依据既有设定和玩家权限裁定。若正文确认恢复已生效，"
            "必须令 worldbook_capture_needed 为 true；失败或无对应规则时为 false。"
        )
    return ""


def capture_instruction(player_action: Any) -> str:
    """Tell the capture-only model how to map an explicit command to CRUD."""
    mode = world_rule_command_mode(player_action)
    if mode == "change":
        return (
            "本回合含显式规则变更命令。仅当正文确认变更已生效时处理：新主题用 add，"
            "替换已有同主题规则用 update；未生效则不输出候选。"
        )
    if mode == "restore":
        return (
            "本回合含显式规则恢复命令。仅当正文确认恢复已生效时处理：只能对准确目标"
            "使用 update 或 retire，禁止 add 一条恢复事件。"
        )
    return ""
