"""Pure request builders for story model tasks.

The caller supplies a read-only snapshot. This module composes model-bound
messages and generation parameters but never reads the active session, calls a
model, or mutates story state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from core.action_suggestions import action_suggestion_instruction
from core.player_agency import adjudication_context, normalize_action_adjudication
from core.preference_learning import preference_context_instruction, preference_learning_instruction
from core.prompt_studio import (
    ModelRequestPlan,
    PromptOverrideStore,
    RequestMessagePart,
    compose_prompt,
    plan_model_request,
)
from core.settlement_prompt_sections import settlement_prompt_baselines
from core.story_length import story_length_instruction


SettlementMode = Literal["normal", "reroll"]
SETTLEMENT_CONTRACT_ID = "story.settlement.v1"
SETTLEMENT_SLICES = {
    "story.settlement.core",
    "story.state.guidance",
    "story.state.contract",
    "story.settlement.player_agency",
    "story.settlement.continuity",
}


@dataclass(frozen=True)
class SettlementRequestSnapshot:
    mode: SettlementMode
    baseline_prompt: str
    context_text: str
    dynamic_state: Mapping[str, Any]
    player_action: str
    visible_world: str
    character_info: str
    style_info: str
    word_limit: int
    story_settings: Mapping[str, Any]
    rule_command_prompt: str
    preference_context: str
    action_adjudication: Mapping[str, Any]
    chosen_description: str
    triggered_influences: Sequence[Mapping[str, Any]]


def _influence_instruction(items: Sequence[Mapping[str, Any]]) -> str:
    return "\n".join(
        f"- [{item['id']}] {item['summary']}；必须体现的后果：{item['effect']}；依据：{item['reason']}"
        for item in items
    ) or "（本回合没有满足条件的暗流影响）"


def _runtime_parts(snapshot: SettlementRequestSnapshot) -> list[tuple[str, str, str]]:
    suggestion = action_suggestion_instruction(snapshot.story_settings.get("aiSuggestions", True))
    preference = preference_context_instruction(snapshot.preference_context)
    parts = {
        "rule": ("story.settlement.world_rule_command", snapshot.rule_command_prompt, "runtime"),
        "length": (
            "story.settlement.length",
            story_length_instruction(snapshot.story_settings.get("targetStoryLength")),
            "runtime",
        ),
        "suggestions": (
            "story.settlement.suggestions",
            ("【玩家行动建议要求】\n" + suggestion) if suggestion else "",
            "runtime",
        ),
        "preference": ("story.settlement.preference_context", preference, "runtime"),
        "learning": (
            "story.settlement.preference_learning",
            preference_learning_instruction(snapshot.preference_context)
            if snapshot.story_settings.get("learnUserPreferences", True)
            else "",
            "runtime",
        ),
    }
    # Preserve each legacy path byte-for-byte in M1. M2 may deliberately
    # normalize this order behind new equivalence and behavior tests.
    order = (
        ("rule", "length", "preference", "learning", "suggestions")
        if snapshot.mode == "normal"
        else ("rule", "length", "suggestions", "preference", "learning")
    )
    return [parts[key] for key in order]


def build_settlement_request(
    snapshot: SettlementRequestSnapshot,
    *,
    store: PromptOverrideStore | None = None,
) -> ModelRequestPlan:
    if snapshot.mode not in {"normal", "reroll"}:
        raise ValueError("未知正文结算模式")
    system = compose_prompt(
        "story.settlement",
        {
            "world_info": snapshot.visible_world,
            "character_info": snapshot.character_info,
            "style_info": snapshot.style_info,
            "word_limit": snapshot.word_limit,
        },
        include=SETTLEMENT_SLICES,
        runtime_parts=_runtime_parts(snapshot),
        baselines=settlement_prompt_baselines(snapshot.baseline_prompt),
        store=store,
    )
    state_text = json.dumps(snapshot.dynamic_state, ensure_ascii=False)
    adjudication = adjudication_context(normalize_action_adjudication(snapshot.action_adjudication))
    influence = _influence_instruction(snapshot.triggered_influences)
    user_parts = (
        RequestMessagePart("story.context.history", f"【情景】：\n{snapshot.context_text}"),
        RequestMessagePart("runtime.state", f"【状态】：{state_text}", "\n"),
        RequestMessagePart("story.player_action", f"【行动】：{snapshot.player_action}", "\n"),
        RequestMessagePart("runtime.adjudication", adjudication, "\n"),
        RequestMessagePart("runtime.selected_future", f"【裁定变数】：{snapshot.chosen_description}", "\n"),
        RequestMessagePart(
            "runtime.triggered_influences",
            f"【本回合必须兑现的暗流影响】：\n{influence}",
            "\n",
        ),
    )
    normal = snapshot.mode == "normal"
    return plan_model_request(
        system,
        user_parts,
        temperature=0.8,
        max_tokens=max(3000, int(snapshot.word_limit * 3)) if normal else 3000,
        trace_label="剧情结算" if normal else "剧情重写",
        mode=snapshot.mode,
        contract_id=SETTLEMENT_CONTRACT_ID,
    )
