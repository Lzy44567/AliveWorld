"""Conversational adapter shared by character, style, and entity workshops."""

from __future__ import annotations

import json
from typing import Any

from core.ai_engine import robust_json_parse
from core.workshop_brief import capture_initial_brief
from core.workshop_context import conversation_context
from core.json_stream import WORKSHOP_FIELDS
from core.asset_workshop import AssetWorkshop, AssetWorkshopError


TYPE_GUIDANCE = {
    "characters": (
        "角色卡工坊。完善人物身份、外观、性格、欲望、矛盾、关系倾向、说话方式和登场情境。"
        "角色要能在故事中稳定扮演，但不要替玩家决定其扮演角色；portrait 不归文本工坊修改。"
    ),
    "styles": (
        "文风卡工坊。把玩家希望的叙事节奏、视角、句式、描写重点、禁忌和示例整理为可执行写作规范。"
        "文风既包含表达方式，也可影响内容关注点，但不要写具体故事事实。"
    ),
    "entities": (
        "暗流实体工坊。只处理具备长期动机、幕后行动能力或持续世界影响的对象。"
        "区分稳定机制、未来计划、已经发生的近期行动、触发器与关系；不要把普通路人或单件道具强行升级为实体。"
    ),
}


SYSTEM_PROMPT = """你是 AliveWorld 资产创作工坊 Agent，不写故事正文。你要像共同设计者一样经历：
理解目标 → 精准澄清 → 比较方案与取舍 → 形成可审阅方案 → 玩家确认后修改草稿。

共同规则：
1. 不要玩家说一句就回复“已经写好”；讨论尚未定稿时 operations 必须为空。
2. 不擅自改资产名称、立绘、因果引用或运行开关，不删除资产。
3. 只允许一个操作格式：{"op":"update_fields","changes":{...},"reason":"修改依据"}。
4. changes 只能使用本轮给出的可编辑字段；每轮提交少量、连贯的修改。可独立审阅的修改分为多个操作；互相依赖的字段保留在同一操作，不拆散完整角色结构。
5. 只讨论与提案权限下，operations 是尚未写入的可审阅方案；允许修改草稿时才可称已经提交。
6. 保留玩家原意，指出歧义、冲突、俗套化风险和信息缺口；最多提出 3 个精准问题、4 个后续建议。
7. 持续参考作者创作目标，不将目标当作人物知识或资产事实。仅在目标为空且玩家未编辑时，可用可选creative_brief字段整理玩家明确表达的目标（最多2000字），不补造、不覆盖已有目标；缺失信息再问，不重复确认已知目标。
8. 输出严格 JSON：
{
  "collaboration_stage":"explore|design|propose|apply",
  "understanding":"对目标与边界的理解",
  "design_notes":["设计依据、取舍或风险"],
  "message":"本轮结论或精准问题",
  "operations":[{"op":"update_fields","changes":{},"reason":"依据"}],
  "suggested_actions":["下一步"]
}
"""


class AssetWorkshopAgent:
    def __init__(self, ai_engine):
        self.ai_engine = ai_engine

    def respond(
        self, workshop: AssetWorkshop, user_message: str, mode: str,
        *, commit_changes: bool = False, on_text_delta=None, history=(),
    ) -> dict[str, Any]:
        if mode not in {"create", "refine", "review"}:
            raise AssetWorkshopError("未知的资产工坊模式")
        structure_rule = (
            "【结构规则】role_fields须保留version=1及完整五项文本；只改要求修改的字段，保留其他原文；示例是表达参考，不是历史。自由卡不可由AI升级/降级结构。\n"
            if workshop.asset_type == 'characters' else ''
        )
        context, context_info = conversation_context(workshop, user_message, history)
        prompt = (
            f"【工坊职责】{TYPE_GUIDANCE[workshop.asset_type]}\n"
            f"【当前工作模式】{mode}\n"
            f"【作者创作目标（不是资产事实）】{workshop.creative_brief or '尚未填写'}\n"
            f"【目标是否由玩家编辑】{workshop.brief_edited}\n"
            f"【可编辑字段】{', '.join(sorted(workshop.ai_fields()))}\n"
            f"{structure_rule}"
            f"【当前草稿】\n{json.dumps(workshop.draft, ensure_ascii=False)}\n"
            f"{context}\n"
            f"【本轮权限】{'允许修改草稿' if commit_changes else '只讨论与提案，不修改草稿'}\n"
            f"【玩家消息】\n{user_message}"
        )
        raw, error = self.ai_engine.chat_json(
            SYSTEM_PROMPT, prompt, temp=0.55,
            trace_label={"characters": "角色卡工坊", "styles": "文风卡工坊", "entities": "实体卡工坊"}[workshop.asset_type],
            **({"on_text_delta": on_text_delta, "visible_fields": WORKSHOP_FIELDS} if on_text_delta is not None else {}),
        )
        if error or not raw:
            raise AssetWorkshopError(f"资产工坊 AI 请求失败：{error or '空返回'}")
        payload = robust_json_parse(raw)
        if not isinstance(payload, dict):
            raise AssetWorkshopError("资产工坊必须返回 JSON 对象")
        capture_initial_brief(workshop, payload, AssetWorkshopError)
        understanding = str(payload.get("understanding", "")).strip()
        notes = [str(item).strip() for item in payload.get("design_notes", []) if str(item).strip()][:4]
        parts = []
        if understanding:
            parts.append("理解\n" + understanding)
        if notes:
            parts.append("设计依据\n" + "\n".join(f"{index}. {item}" for index, item in enumerate(notes, 1)))
        parts.append("结论\n" + (str(payload.get("message", "")).strip() or "本轮讨论已记录。"))
        message = "\n\n".join(parts)
        operations = payload.get("operations", [])
        operations = operations if isinstance(operations, list) else []
        suggestions = [str(item).strip() for item in payload.get("suggested_actions", []) if str(item).strip()][:4]
        workshop.suggested_actions = suggestions
        if commit_changes:
            workshop.clear_proposal()
            result = workshop.apply_operations(operations, actor="ai")
            proposed = []
        else:
            proposed = workshop.propose_operations(operations)
            result = {"applied": [], "draft": workshop.draft}
        workshop.messages.extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": message},
        ])
        workshop.touch()
        return {
            "context_info": context_info,
            "message": message, "suggested_actions": suggestions,
            "applied": result["applied"], "proposed": proposed, "draft": result["draft"],
        }
