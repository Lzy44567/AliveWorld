"""Conversational AI adapter for the user preference workshop."""

from __future__ import annotations

import json
from typing import Any

from core.ai_engine import robust_json_parse
from core.preference_workshop import PreferenceWorkshop, PreferenceWorkshopError


MODES = {
    "discover": "结合玩家自述与证据，探索可能的体验偏好，但保留竞争解释",
    "refine": "修正现有偏好的措辞、分类、边界和适用范围",
    "balance": "检查偏好之间的冲突、过度重复风险和内容多样性",
}


SYSTEM_PROMPT = """你是 AliveWorld 用户偏好工坊 Agent。你协助玩家理解和整理自己的游戏体验偏好，不写故事正文，不做心理诊断。

协作原则：
1. 像可靠的共同设计者一样经历“理解目标 → 区分解释 → 讨论取舍 → 提出方案 → 玩家审阅 → 写入草稿”，不要玩家说一句就回复“已经写好”。
2. 行为证据不是心理结论。重掷、撤回、重试和重新生图都有许多替代原因；必须保留不确定性。
3. 玩家明确自述是高先验，但仍可能表述不完整。帮助区分表面内容与期望的心理回报，例如“想要强大角色”可能涉及掌控感、旁观反馈、审美或求胜。
4. 不要为了显得有产出而新增大量偏好。优先修正或细化已有条目，最多提出 4 个操作。
5. 偏好用于调整出现倾向，不意味着每回合重复满足。主动指出审美疲劳、冲突或需要留白的地方。
6. category 只能是 story、adult、action、character、relationship、visual、boundary、other；polarity 只能是 prefer 或 avoid。
7. 你不能修改 posterior、confidence、evidence_count 或证据。只能使用 add_preference、update_preference、set_status、delete_preference。
8. 新的自动推断默认 status=candidate。只有玩家明确确认“这是我的偏好”时才可建议 active；启用和删除都会由系统要求确认。
9. 玩家只是在讨论、询问原因或尚未定稿时，operations 必须为空。权限为“只讨论与提案”时，操作也只是待审方案，不能声称已经写入。
10. 输出应承接近期对话，不重复从零分析。最多给 4 个下一步建议。

严格输出 JSON：
{
  "collaboration_stage": "explore|design|propose|apply",
  "understanding": "对玩家目标、边界和不确定性的具体理解",
  "alternative_explanations": ["还可能怎样解释"],
  "design_notes": ["表述、分类、冲突、多样性或取舍"],
  "message": "本轮结论或需要确认的精准问题",
  "operations": [
    {"op":"add_preference","preference":{"statement":"偏好表述","category":"story","polarity":"prefer","status":"candidate","sensitive":false}},
    {"op":"update_preference","preference_id":"preference_xxx","changes":{"statement":"新表述","category":"relationship"}},
    {"op":"set_status","preference_id":"preference_xxx","status":"active"},
    {"op":"delete_preference","preference_id":"preference_xxx"}
  ],
  "suggested_actions": ["下一步讨论或确认方向"]
}
"""


class PreferenceWorkshopAgent:
    def __init__(self, ai_engine):
        self.ai_engine = ai_engine

    def respond(
        self,
        workshop: PreferenceWorkshop,
        user_message: str,
        mode: str,
        evidence: list[dict[str, Any]],
        *,
        commit_changes: bool = False,
    ) -> dict[str, Any]:
        if mode not in MODES:
            raise PreferenceWorkshopError("未知的偏好工坊模式")
        safe_evidence = [
            {
                key: item.get(key)
                for key in ("id", "save_name", "signal_type", "summary", "context", "diagnosticity", "sensitive")
            }
            for item in evidence[-30:]
            if workshop.include_sensitive or not item.get("sensitive")
        ]
        safe_draft = [
            {
                key: item.get(key)
                for key in (
                    "id", "statement", "category", "polarity", "status",
                    "sensitive", "source_type", "confidence", "evidence_count",
                )
            }
            for item in workshop.draft
            if workshop.include_sensitive or not item.get("sensitive")
        ]
        prompt = (
            f"【当前模式】{MODES[mode]}\n"
            f"【偏好草稿摘要】\n{json.dumps(safe_draft, ensure_ascii=False)}\n"
            f"【可用行为证据】\n{json.dumps(safe_evidence, ensure_ascii=False)}\n"
            f"【近期工坊对话】\n{json.dumps(workshop.messages[-12:], ensure_ascii=False)}\n"
            f"【本轮权限】\n{'允许低风险修改草稿；启用和删除仍等待确认' if commit_changes else '只讨论与提案；不得改变草稿'}\n"
            f"【玩家本轮消息】\n{user_message}"
        )
        raw, error = self.ai_engine.chat_json(
            SYSTEM_PROMPT, prompt, temp=0.45, max_tokens=2600, trace_label="用户偏好工坊"
        )
        if error or not raw:
            raise PreferenceWorkshopError(f"偏好工坊 AI 请求失败：{error or '空返回'}")
        payload = robust_json_parse(raw)
        if not isinstance(payload, dict):
            raise PreferenceWorkshopError("偏好工坊必须返回 JSON 对象")
        stage = str(payload.get("collaboration_stage", "design")).lower()
        if stage not in {"explore", "design", "propose", "apply"}:
            stage = "design"
        parts = []
        understanding = str(payload.get("understanding", "")).strip()
        alternatives = [str(item).strip() for item in payload.get("alternative_explanations", []) if str(item).strip()][:4]
        notes = [str(item).strip() for item in payload.get("design_notes", []) if str(item).strip()][:4]
        if understanding:
            parts.append("理解\n" + understanding)
        if alternatives:
            parts.append("仍需保留的其他解释\n" + "\n".join(f"{i}. {item}" for i, item in enumerate(alternatives, 1)))
        if notes:
            parts.append("设计取舍\n" + "\n".join(f"{i}. {item}" for i, item in enumerate(notes, 1)))
        parts.append("结论\n" + (str(payload.get("message", "")).strip() or "本轮讨论已记录。"))
        message = "\n\n".join(parts)
        operations = payload.get("operations", [])
        operations = operations if isinstance(operations, list) else []
        suggestions = [str(item).strip() for item in payload.get("suggested_actions", []) if str(item).strip()][:4]
        workshop.suggested_actions = suggestions
        if commit_changes:
            workshop.clear_proposal()
            result = workshop.apply_operations(operations)
            proposed = []
        else:
            proposed = workshop.propose_operations(operations)
            result = {"applied": [], "pending": [], "draft": workshop.draft}
        workshop.messages.extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": message},
        ])
        workshop.touch()
        return {
            "message": message, "collaboration_stage": stage, "suggested_actions": suggestions,
            "applied": result["applied"], "pending": result["pending"],
            "proposed": proposed, "draft": result["draft"],
        }
