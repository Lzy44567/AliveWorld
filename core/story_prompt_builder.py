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
from core.preference_learning import (
    preference_context_data,
    preference_context_guidance,
    preference_learning_instruction,
)
from core.prompt_studio import (
    ModelRequestPlan,
    PromptOverrideStore,
    RequestMessagePart,
    RuntimePromptPart,
    active_slice_variables,
    compose_prompt,
    plan_model_request,
)
from core.settlement_prompt_sections import settlement_prompt_baselines
from core.story_experience import ENGINE_ONLY_EXPERIENCE, normalize_story_experience
from core.story_length import story_length_instruction
from core.effect_progress import (
    FUTURE_EFFECT_INSTRUCTION, SETTLEMENT_EFFECT_INSTRUCTION, needs_effect_progress,
)
from core.npc_identity import NPC_IDENTITY_INSTRUCTION


SettlementMode = Literal["normal", "reroll"]
FUTURE_CONTRACT_ID = "story.future.v1"
SETTLEMENT_CONTRACT_ID = "story.settlement.v2"
FUTURE_SLICES = {
    "story.future.core",
    "story.future.player_agency",
    "story.future.continuity",
}
FUTURE_EXPERIENCE_SLICE = "story.future.experience"
SETTLEMENT_SLICES = {
    "story.settlement.core",
    "story.state.guidance",
    "story.state.contract",
    "story.settlement.player_agency",
    "story.settlement.continuity",
}
SETTLEMENT_EXPERIENCE_SLICE = "story.settlement.experience"


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
    effect_report: Mapping[str, Any] | None = None
    npc_identities: Sequence[Mapping[str, Any]] = ()


@dataclass(frozen=True)
class FutureRequestSnapshot:
    baseline_prompt: str
    context_text: str
    dynamic_state: Mapping[str, Any]
    player_action: str
    visible_world: str
    character_info: str
    causal_context: str
    rule_command_prompt: str
    story_settings: Mapping[str, Any]


def _experience_slice(base: set[str], slice_id: str, settings: Mapping[str, Any]) -> set[str]:
    selected = normalize_story_experience(settings.get("storyExperiencePreset"))
    return set(base) if selected == ENGINE_ONLY_EXPERIENCE else {*base, slice_id}


def build_future_request(
    snapshot: FutureRequestSnapshot,
    *,
    store: PromptOverrideStore | None = None,
) -> ModelRequestPlan:
    baselines = {"story.future.core": snapshot.baseline_prompt}
    embedded = active_slice_variables(
        "story.future.core", store=store, baselines=baselines,
    )
    legacy_world = (
        snapshot.visible_world + "\n【隐藏的暗流因果】：\n" + snapshot.causal_context
    )
    system = compose_prompt(
        "story.future",
        {
            "world_info": legacy_world,
            "character_info": snapshot.character_info,
        },
        include=_experience_slice(
            FUTURE_SLICES, FUTURE_EXPERIENCE_SLICE, snapshot.story_settings,
        ),
        runtime_parts=[RuntimePromptPart(
            "story.future.world_rule_command",
            snapshot.rule_command_prompt,
            layer="feature",
            cache_class="turn",
        ), RuntimePromptPart(
            "story.future.effect_progress",
            FUTURE_EFFECT_INSTRUCTION if needs_effect_progress(snapshot.dynamic_state) else "",
            layer="contract", cache_class="configuration",
        )],
        baselines=baselines,
        store=store,
    )
    user_parts: list[RequestMessagePart] = []
    if "context.player_character" not in embedded and snapshot.character_info:
        user_parts.append(RequestMessagePart(
            "context.player_character",
            f"【玩家角色设定】：\n{snapshot.character_info}",
            cache_class="asset",
        ))
    user_parts.append(RequestMessagePart(
        "story.history", f"【情景】：\n{snapshot.context_text}",
        "\n" if user_parts else "", "session",
    ))
    if "context.world" not in embedded:
        if snapshot.visible_world:
            user_parts.append(RequestMessagePart(
                "context.world.visible",
                f"【本回合可见世界资料】：\n{snapshot.visible_world}",
                "\n",
                "turn",
            ))
        if snapshot.causal_context:
            user_parts.append(RequestMessagePart(
                "runtime.causal_candidates",
                f"【待判断的隐藏暗流因果】：\n{snapshot.causal_context}",
                "\n",
            ))
    user_parts.extend((
        RequestMessagePart(
            "runtime.state",
            f"【状态】：{json.dumps(snapshot.dynamic_state, ensure_ascii=False)}",
            "\n",
        ),
        RequestMessagePart("story.player_action", f"【行动】：{snapshot.player_action}", "\n"),
    ))
    return plan_model_request(
        system,
        user_parts,
        temperature=0.7,
        max_tokens=None,
        trace_label="变数推演",
        mode="normal",
        contract_id=FUTURE_CONTRACT_ID,
    )


def _influence_instruction(items: Sequence[Mapping[str, Any]]) -> str:
    return "\n".join(
        f"- [{item['id']}] {item['summary']}；必须体现的后果：{item['effect']}；依据：{item['reason']}"
        for item in items
    ) or "（本回合没有满足条件的暗流影响）"


def _runtime_parts(snapshot: SettlementRequestSnapshot) -> list[RuntimePromptPart]:
    suggestion = action_suggestion_instruction(snapshot.story_settings.get("aiSuggestions", True))
    parts = [
        RuntimePromptPart('story.state.npc_identity', NPC_IDENTITY_INSTRUCTION,
                          layer='contract', cache_class='static'),
        RuntimePromptPart(
            "story.state.effect_definition",
            "【持续效果定义】new_buffs的duration是后续剩余结算次数，新增效果不追溯结算本次已过去时间。"
            "有明确故事时间周期时附tick_seconds正整数秒数，不随意推定战斗轮秒数；tick_elapsed由程序维护。",
            layer="contract", cache_class="static",
        ),
        RuntimePromptPart(
            "story.settlement.effect_progress",
            SETTLEMENT_EFFECT_INSTRUCTION if snapshot.effect_report is not None else "",
            layer="contract", cache_class="configuration",
        ),
        RuntimePromptPart(
            "story.settlement.length",
            story_length_instruction(snapshot.story_settings.get("targetStoryLength")),
            layer="feature",
            cache_class="configuration",
        ),
        RuntimePromptPart(
            "story.settlement.preference_guidance",
            preference_context_guidance(snapshot.preference_context),
            layer="feature",
            cache_class="configuration",
        ),
        RuntimePromptPart(
            "story.settlement.preference_learning",
            preference_learning_instruction(snapshot.preference_context)
            if snapshot.story_settings.get("learnUserPreferences", True)
            else "",
            layer="feature",
            cache_class="configuration",
        ),
        RuntimePromptPart(
            "story.settlement.suggestions",
            ("【玩家行动建议要求】\n" + suggestion) if suggestion else "",
            layer="feature",
            cache_class="configuration",
        ),
        RuntimePromptPart(
            "story.settlement.world_rule_command",
            snapshot.rule_command_prompt,
            layer="feature",
            cache_class="turn",
        ),
    ]
    return parts


def build_settlement_request(
    snapshot: SettlementRequestSnapshot,
    *,
    store: PromptOverrideStore | None = None,
) -> ModelRequestPlan:
    if snapshot.mode not in {"normal", "reroll"}:
        raise ValueError("未知正文结算模式")
    baselines = settlement_prompt_baselines(snapshot.baseline_prompt)
    embedded = active_slice_variables(
        "story.settlement.core", store=store, baselines=baselines,
    )
    system = compose_prompt(
        "story.settlement",
        {
            "world_info": snapshot.visible_world,
            "character_info": snapshot.character_info,
            "style_info": snapshot.style_info,
            "word_limit": snapshot.word_limit,
        },
        include=({"story.world_changes"} if snapshot.story_settings.get("worldbookCaptureEnabled", True) else set()) | _experience_slice(
            SETTLEMENT_SLICES, SETTLEMENT_EXPERIENCE_SLICE, snapshot.story_settings,
        ),
        runtime_parts=_runtime_parts(snapshot),
        baselines=baselines,
        store=store,
    )
    state_text = json.dumps(snapshot.dynamic_state, ensure_ascii=False)
    adjudication = adjudication_context(normalize_action_adjudication(snapshot.action_adjudication))
    influence = _influence_instruction(snapshot.triggered_influences)
    user_parts: list[RequestMessagePart] = []
    for variable_id, value, label, cache_class in (
        ("context.style", snapshot.style_info, "文风指导", "asset"),
        ("context.player_character", snapshot.character_info, "玩家角色设定", "asset"),
        (
            "player.preferences.confirmed",
            preference_context_data(snapshot.preference_context),
            "",
            "session",
        ),
    ):
        if variable_id not in embedded and value:
            user_parts.append(RequestMessagePart(
                "context.world.visible" if variable_id == "context.world" else variable_id,
                value if not label else f"【{label}】：\n{value}",
                "\n" if user_parts else "",
                cache_class,
            ))
    user_parts.append(RequestMessagePart(
        "story.history", f"【情景】：\n{snapshot.context_text}",
        "\n" if user_parts else "", "session",
    ))
    if "context.world" not in embedded and snapshot.visible_world:
        user_parts.append(RequestMessagePart(
            "context.world.visible",
            f"【本回合可见世界资料】：\n{snapshot.visible_world}",
            "\n",
            "turn",
        ))
    user_parts.extend((
        RequestMessagePart("runtime.state", f"【状态】：{state_text}", "\n"),
        RequestMessagePart("story.player_action", f"【行动】：{snapshot.player_action}", "\n"),
        RequestMessagePart("runtime.adjudication", adjudication, "\n"),
        RequestMessagePart("runtime.selected_future", f"【裁定变数】：{snapshot.chosen_description}", "\n"),
        RequestMessagePart(
            "runtime.triggered_influences",
            f"【本回合必须兑现的暗流影响】：\n{influence}",
            "\n",
        ),
    ))
    if snapshot.effect_report is not None:
        user_parts.append(RequestMessagePart(
            "runtime.effect_progress",
            "【runtime.effect_progress 程序结算报告】：" + json.dumps(snapshot.effect_report, ensure_ascii=False),
            "\n",
        ))
    if snapshot.npc_identities:
        user_parts.append(RequestMessagePart(
            'runtime.npc_identities', '【本局已知人物身份】：' + json.dumps(snapshot.npc_identities, ensure_ascii=False), '\n',
        ))
    normal = snapshot.mode == "normal"
    return plan_model_request(
        system,
        user_parts,
        temperature=0.8,
        max_tokens=None,  # Reading-length guidance is independent of the connection's output budget.
        trace_label="剧情结算" if normal else "剧情重写",
        mode=snapshot.mode,
        contract_id=SETTLEMENT_CONTRACT_ID,
    )
