"""Player agency and turn fact-adjudication prompt contract."""

from __future__ import annotations

from typing import Any


PLAYER_AGENCY_RULES = """【玩家行动权与事实裁定】
玩家输入不是等待你反驳的角色台词。先区分“玩家有权确定的事实”和“需要世界裁定的外部结果”：
1. 玩家角色主动说了什么、想了什么、尝试或完成了什么身体动作，由玩家决定；不得擅自改成没有行动、只是幻想、说谎、认命、精神崩溃或做出相反选择。
2. 玩家明确补充的自身背景、既有能力、持有物和括号内纠错，默认成为当前故事事实。只有它直接违反已明确注入的绝对世界规则或已锁定硬条件时才能质疑，并必须指出具体冲突依据；“现实中不可能”或“上一段模型曾否认”本身不是依据。
3. 玩家不能替独立 NPC 决定意愿，也不能无条件决定攻击必定命中、敌人必死、机关必毁等外部结果。这些部分进入 contested_outcomes，由世界规则、状态、NPC能力和随机候选裁定。
4. 一句话同时包含动作与外部结果时，只裁定外部结果。例如“我发射球状闪电摧毁囚车”：若球状闪电能力已由玩家补充且无绝对规则冲突，则“成功发射”是 accepted_facts；囚车是否摧毁才是 contested_outcomes。不得把整句降级为“什么也没发生”。
5. 玩家本回合的明确纠错优先于旧正文中由模型擅自添加、且没有世界书或玩家输入支持的描述。候选从 accepted_facts 已经发生之后开始分化，不得用候选倒写或抹除这些事实。
6. 不替玩家追加投降、逃跑、攻击、原谅、羞愧、崩溃等重大决定。可以描写动作的直接感官反馈，但新的决定必须留给玩家。"""


ACTION_ADJUDICATION_SCHEMA = """在 JSON 顶层返回：
"action_adjudication": {
  "accepted_facts": ["本回合必须保留的玩家行动、纠错或自身事实"],
  "contested_outcomes": [{"claim": "需要裁定的外部结果", "reason": "为什么不由玩家单方面决定"}],
  "rejected_claims": [{"claim": "确实违反硬条件的主张", "basis": "明确的绝对规则或锁定事实；不得只写现实中不可能"}]
}
没有对应内容时使用空数组。"""


def player_agency_instruction(*, require_output: bool = True) -> str:
    if require_output:
        return f"{PLAYER_AGENCY_RULES}\n\n{ACTION_ADJUDICATION_SCHEMA}"
    return PLAYER_AGENCY_RULES


def _text_list(value: Any, limit: int = 12) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value[:limit]:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text[:500])
    return result


def _claim_list(value: Any, *, reason_key: str, limit: int = 8) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, str]] = []
    for item in value[:limit]:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim", "")).strip()[:500]
        reason = str(item.get(reason_key, "")).strip()[:500]
        if claim:
            result.append({"claim": claim, reason_key: reason})
    return result


def normalize_action_adjudication(value: Any) -> dict[str, Any]:
    """Normalize an optional model adjudication without trusting arbitrary fields."""
    value = value if isinstance(value, dict) else {}
    return {
        "accepted_facts": _text_list(value.get("accepted_facts")),
        "contested_outcomes": _claim_list(value.get("contested_outcomes"), reason_key="reason"),
        "rejected_claims": _claim_list(value.get("rejected_claims"), reason_key="basis"),
    }


def adjudication_context(value: Any) -> str:
    adjudication = normalize_action_adjudication(value)
    accepted = adjudication["accepted_facts"]
    contested = adjudication["contested_outcomes"]
    rejected = adjudication["rejected_claims"]
    lines = ["【本回合行动事实裁定】"]
    lines.append("已接受，正文不得否认：" + ("；".join(accepted) if accepted else "无额外声明"))
    lines.append("待由所选未来决定：" + ("；".join(item["claim"] for item in contested) if contested else "无"))
    if rejected:
        lines.append("因明确硬条件拒绝：" + "；".join(f"{item['claim']}（{item['basis']}）" for item in rejected))
    lines.append("正文必须从上述裁定之后续写，不得重新解释或推翻已接受事实，也不得替玩家新增重大决定。")
    return "\n".join(lines)
