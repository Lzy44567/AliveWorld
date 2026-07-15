"""AI adapter for worldbook workshop conversations."""

from __future__ import annotations

import json
from typing import Any

from core.ai_engine import robust_json_parse
from core.worldbook_workshop import WorldbookWorkshop, WorkshopError


MODES = {
    "create": "从玩家的一句话和偏好建立或重构世界书框架",
    "expand": "横向拓展新领域，补充此前没有覆盖的主题和条目",
    "evolve": "从已有公理和规则推导逻辑后果，完善设定体系",
}


SYSTEM_PROMPT = """你是 AliveWorld 世界书工坊 Agent。你只协助开发当前给出的世界书草稿，不写故事正文。你的价值不是快速堆设定，而是与玩家共同完成“理解目标 → 讨论取舍 → 提出方案 → 审阅后写入”的创作流程。

工作要求：
1. 区分拓展（新增主题）与演化（从已有规则推导后果）。
2. 演化建议必须说明前提、中间影响和新设定，不能只说抽象的相关性。
3. 尊重玩家本次创作偏好；不擅自把角色台词、传闻或猜测升级为客观真相。
4. 不覆盖整本世界书。每轮只提交少量、可审查的操作。
5. 新公理或绝对规则在操作中设置 creates_axiom=true，系统会要求玩家确认。
6. 可使用 add_entry、update_entry、deactivate_entry、request_delete、update_overview、set_axioms。不得请求文件、路径、代码或其他资产操作。
7. 建议玩家下一步可以继续讨论的方向，最多 4 项。
8. 新条目的 tags 必须包含来源标签“AI推断”，并至少增加一个描述内容领域的自由标签，例如“法律”“学校”“服装”“魔法”。不要只写“AI推断”。
9. 玩家要求修改指定条目时，必须使用草稿中该条目的 entry_id 执行 update_entry，不要另建同义条目。
10. 先说明你对玩家目标的理解，再列出 1-4 条与既有概述、公理、条目的关系、推导依据或取舍。不要只回复“好的，已经写好”。
11. 如果玩家的要求存在会显著改变世界基调的歧义，先提出最多 3 个精准问题，此时 operations 可以为空；不要用大量开放问题拖延明确需求。
12. 本轮权限为“只讨论与提案”时，operations 代表可审阅的拟议修改，系统不会立刻写入；措辞必须明确“尚未写入”。本轮权限为“允许修改草稿”时，才能称低风险操作已经提交，高风险操作仍只能称“等待确认”。
13. set_axioms 必须返回每条完整公理。公理应是简洁、稳定、能够推导其他设定的底层规则，避免把具体案例或单件道具提升为公理。
14. suggested_actions 应延续当前设计决策，例如补充依据、比较方案或确认写入，不要无缘无故跳到全新领域。
15. 将协作视为连续对话，而不是一次性生成器。根据本轮实际进度选择 explore（澄清目标）、design（比较和推导）、propose（形成可写入方案）或 apply（按已确认方案修改）。玩家只是在讨论、询问可行性或尚未定稿时，operations 必须为空。
16. 不要为了显得有产出而每轮新增条目。只有玩家明确要求形成草稿修改，或近期对话已经就具体方案达成一致时，才生成 operations；否则继续讨论关键取舍。
17. 回答应承接近期对话中已经确认的内容，不重复从零介绍，也不要把 AI 自己刚提出、玩家尚未认可的假设当成共识。

严格输出 JSON：
{
  "collaboration_stage": "explore|design|propose|apply",
  "understanding": "你对玩家目标和边界的具体理解",
  "design_notes": ["与既有设定的关系、推导依据、冲突或取舍"],
  "message": "本轮结论、需要确认的问题或下一步说明",
  "operations": [
    {"op":"add_entry","entry":{"name":"名称","keys":"可选关键词","content":"内容","tags":["AI推断","内容领域标签"]},"creates_axiom":false},
    {"op":"update_entry","entry_id":"entry_xxx","changes":{"content":"新内容"},"creates_axiom":false},
    {"op":"update_overview","overview":"新的世界概述"},
    {"op":"set_axioms","axioms":["公理一"]}
  ],
  "suggested_actions": ["下一步建议"]
}
"""


class WorldbookWorkshopAgent:
    def __init__(self, ai_engine):
        self.ai_engine = ai_engine

    def respond(self, workshop: WorldbookWorkshop, user_message: str, mode: str, *, commit_changes: bool = False) -> dict[str, Any]:
        if mode not in MODES:
            raise WorkshopError("未知的世界书工坊模式")
        recent = workshop.messages[-10:]
        prompt = (
            f"【当前模式】{MODES[mode]}\n"
            f"【当前世界书草稿】\n{json.dumps(workshop.draft, ensure_ascii=False)}\n"
            f"【近期工坊对话】\n{json.dumps(recent, ensure_ascii=False)}\n"
            f"【本轮协作权限】\n{'允许修改草稿：低风险操作可写入，高风险操作仍需玩家确认' if commit_changes else '只讨论与提案：operations 仅作为拟议修改展示，不得声称已经写入'}\n"
            f"【玩家本轮要求】\n{user_message}"
        )
        raw, error = self.ai_engine.chat_json(SYSTEM_PROMPT, prompt, temp=0.6, trace_label="世界书工坊")
        if error or not raw:
            raise WorkshopError(f"世界书工坊 AI 请求失败：{error or '空返回'}")
        payload = robust_json_parse(raw)
        stage = str(payload.get("collaboration_stage", "design")).strip().lower()
        if stage not in {"explore", "design", "propose", "apply"}:
            stage = "design"
        understanding = str(payload.get("understanding", "")).strip()
        design_notes = [str(item).strip() for item in payload.get("design_notes", []) if str(item).strip()][:4]
        conclusion = str(payload.get("message", "")).strip() or "本轮建议已生成。"
        parts = []
        if understanding:
            parts.append(f"理解\n{understanding}")
        if design_notes:
            parts.append("设计依据\n" + "\n".join(f"{index}. {item}" for index, item in enumerate(design_notes, 1)))
        parts.append(f"结论\n{conclusion}")
        message = "\n\n".join(parts)
        operations = payload.get("operations", [])
        suggestions = [str(item).strip() for item in payload.get("suggested_actions", []) if str(item).strip()][:4]
        workshop.suggested_actions = suggestions
        operations = operations if isinstance(operations, list) else []
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
            "message": message,
            "collaboration_stage": stage,
            "suggested_actions": suggestions,
            "applied": result["applied"],
            "pending": result["pending"],
            "proposed": proposed,
            "draft": result["draft"],
        }
