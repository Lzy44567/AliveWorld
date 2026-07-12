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


SYSTEM_PROMPT = """你是 AliveWorld 世界书工坊 Agent。你只协助开发当前给出的世界书草稿，不写故事正文。

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

严格输出 JSON：
{
  "message": "给玩家看的自然语言解释",
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

    def respond(self, workshop: WorldbookWorkshop, user_message: str, mode: str) -> dict[str, Any]:
        if mode not in MODES:
            raise WorkshopError("未知的世界书工坊模式")
        recent = workshop.messages[-10:]
        prompt = (
            f"【当前模式】{MODES[mode]}\n"
            f"【当前世界书草稿】\n{json.dumps(workshop.draft, ensure_ascii=False)}\n"
            f"【近期工坊对话】\n{json.dumps(recent, ensure_ascii=False)}\n"
            f"【玩家本轮要求】\n{user_message}"
        )
        raw, error = self.ai_engine.chat_json(SYSTEM_PROMPT, prompt, temp=0.6, trace_label="世界书工坊")
        if error or not raw:
            raise WorkshopError(f"世界书工坊 AI 请求失败：{error or '空返回'}")
        payload = robust_json_parse(raw)
        message = str(payload.get("message", "")).strip() or "本轮建议已生成。"
        operations = payload.get("operations", [])
        suggestions = [str(item).strip() for item in payload.get("suggested_actions", []) if str(item).strip()][:4]
        result = workshop.apply_operations(operations if isinstance(operations, list) else [])
        workshop.messages.extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": message},
        ])
        workshop.touch()
        return {
            "message": message,
            "suggested_actions": suggestions,
            "applied": result["applied"],
            "pending": result["pending"],
            "draft": result["draft"],
        }
