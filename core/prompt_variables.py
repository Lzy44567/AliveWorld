"""Canonical prompt-variable metadata and legacy alias resolution.

The registry describes model-bound context without owning story data. Domain
owners still provide read-only values when a prompt is composed.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PromptVariable:
    id: str
    label: str
    description: str
    value_type: str
    owner: str
    allowed_tasks: tuple[str, ...]
    empty_behavior: str
    sensitivity: str
    renderer: str
    cache_class: str
    legacy_aliases: tuple[str, ...] = ()

    @property
    def syntax(self) -> str:
        return "{{" + self.id + "}}"

    def view(self) -> dict:
        value = asdict(self)
        value["allowedTasks"] = list(value.pop("allowed_tasks"))
        value["emptyBehavior"] = value.pop("empty_behavior")
        value["cacheClass"] = value.pop("cache_class")
        value["legacyAliases"] = list(value.pop("legacy_aliases"))
        value["syntax"] = self.syntax
        return value


VARIABLES: tuple[PromptVariable, ...] = (
    PromptVariable(
        "context.world", "世界与当前因果上下文",
        "旧版聚合变量。按任务提供世界规则及允许的因果内容；新提示词优先使用更明确的资料投影。",
        "text", "story_context", ("story.future", "story.settlement"), "empty_text",
        "story_private", "plain_text", "session", ("world_info",),
    ),
    PromptVariable(
        "context.world.visible", "本回合可见世界资料",
        "经过世界书检索和权限过滤、本任务可以读取的世界规则与NPC设定；不包含隐藏暗流账本。",
        "text", "story_context", ("story.future", "story.settlement"), "empty_text",
        "story_private", "plain_text", "turn", (),
    ),
    PromptVariable(
        "context.player_character", "玩家角色设定",
        "当前由玩家扮演的角色资料。没有载入玩家角色卡时为空，不代表模型可以替玩家决定性格或行动。",
        "text", "character_context", ("story.future", "story.settlement"), "empty_text",
        "story_private", "plain_text", "asset", ("character_info",),
    ),
    PromptVariable(
        "context.style", "正文文风指导",
        "当前故事已启用的文风卡内容；为空时使用模型的自然叙事风格。",
        "text", "style_context", ("story.settlement",), "empty_text",
        "story_private", "plain_text", "asset", ("style_info",),
    ),
    PromptVariable(
        "context.active_entities", "活跃暗流实体",
        "当前允许参与幕后推演的实体摘要；封存实体和未授权的隐藏字段不会进入这里。",
        "text", "entity_context", ("undercurrent",), "empty_text",
        "hidden_system", "plain_text", "session", ("entities_info",),
    ),
    PromptVariable(
        "context.undercurrent_world", "暗流世界上下文",
        "供幕后实体推演使用的世界规则、近期剧情与既有暗流，不应直接展示给玩家或生图任务。",
        "text", "undercurrent", ("undercurrent",), "empty_text",
        "hidden_system", "plain_text", "session", ("world_context",),
    ),
    PromptVariable(
        "settings.story_length", "目标正文长度",
        "玩家为本故事设置的正文目标长度。它是篇幅指导，不要求模型机械凑字数。",
        "number", "story_settings", ("story.settlement",), "omit",
        "public", "integer", "configuration", ("target_story_length", "word_limit"),
    ),
    PromptVariable(
        "settings.action_suggestions", "快捷行动按钮状态",
        "是否要求正文结算同时返回快捷行动建议；关闭后相关可选提示词应完全不发送。",
        "boolean", "story_settings", ("story.settlement",), "omit",
        "public", "boolean", "configuration", ("enabled",),
    ),
    PromptVariable(
        "story.history", "近期故事上下文",
        "由记忆系统组装的摘要与近期完整回合，用于从当前故事位置继续；不会改写永久保存的原文。",
        "text", "story_memory", ("story.future", "story.settlement"), "empty_text",
        "story_private", "plain_text", "session", (),
    ),
    PromptVariable(
        "runtime.state", "本回合状态快照",
        "玩家状态条、文字状态、Buff和当前场景NPC的只读快照；模型只能通过输出契约提出更新。",
        "json", "state_manager", ("story.future", "story.settlement"), "empty_json",
        "story_private", "json", "turn", (),
    ),
    PromptVariable(
        "story.player_action", "玩家本回合行动",
        "玩家当前提交并已展开快捷选项引用的行动。它靠近消息末尾，作为本回合推演的直接输入。",
        "text", "game_session", ("story.future", "story.settlement"), "error",
        "story_private", "plain_text", "turn", (),
    ),
    PromptVariable(
        "runtime.causal_candidates", "待判断的隐藏因果",
        "仅供近期未来判断触发条件的受控暗流投影；正文GM不会读取未触发的完整账本。",
        "text", "causal_ledger", ("story.future",), "empty_text",
        "hidden_system", "plain_text", "turn", (),
    ),
    PromptVariable(
        "runtime.adjudication", "行动事实裁定",
        "近期未来对玩家事实、外部结果和硬冲突的结构化裁定；正文必须从该裁定之后续写。",
        "json", "future_resolution", ("story.settlement",), "error",
        "hidden_system", "json", "turn", (),
    ),
    PromptVariable(
        "runtime.selected_future", "选中的近期未来",
        "Python从合格候选中完成物理随机后选中的唯一未来；正文不读取未选候选全集。",
        "text", "future_resolution", ("story.settlement",), "error",
        "hidden_system", "plain_text", "turn", (),
    ),
    PromptVariable(
        "runtime.triggered_influences", "本回合已触发暗流",
        "经未来判断和代码ID校验后，本回合正文必须兑现的影响；为空表示没有已触发影响。",
        "json", "causal_ledger", ("story.settlement",), "empty_json",
        "hidden_system", "json", "turn", (),
    ),
    PromptVariable(
        "player.preferences.confirmed", "已确认玩家偏好",
        "玩家已经确认或达到展示门槛的偏好数据；只影响呈现和关注重点，关闭偏好卡后为空。",
        "text", "user_preferences", ("story.settlement",), "omit",
        "story_private", "plain_text", "session", (),
    ),
    PromptVariable("character.presentation_mode", "角色会话表现模式", "本轮即时聊天或情景扮演模式，不改变身份。",
                   "text", "character_chat", ("character.reply",), "empty_text", "public", "plain_text", "configuration"),
)

VARIABLE_BY_ID = {item.id: item for item in VARIABLES}
VARIABLE_BY_ALIAS = {alias: item for item in VARIABLES for alias in item.legacy_aliases}


def require_variable(variable_id: str) -> PromptVariable:
    try:
        return VARIABLE_BY_ID[variable_id]
    except KeyError as exc:
        raise KeyError(f"未知提示词变量：{variable_id}") from exc


def resolve_variable(name: str) -> PromptVariable | None:
    return VARIABLE_BY_ID.get(name) or VARIABLE_BY_ALIAS.get(name)


def normalize_values(values: dict[str, object]) -> dict[str, object]:
    """Accept canonical IDs and legacy call-site names during migration."""
    normalized: dict[str, object] = {}
    # Canonical values are authoritative even when a legacy caller happens to
    # provide the old alias first.
    for name, value in values.items():
        definition = VARIABLE_BY_ID.get(name)
        if definition:
            normalized[definition.id] = value
    for name, value in values.items():
        definition = VARIABLE_BY_ALIAS.get(name)
        if definition:
            normalized.setdefault(definition.id, value)
    return normalized


def render_variable(template: str, definition: PromptVariable, value: object) -> str:
    rendered = re.sub(
        r"\{\{\s*" + re.escape(definition.id) + r"\s*\}\}",
        lambda _match: str(value),
        template,
    )
    for alias in definition.legacy_aliases:
        rendered = rendered.replace("{" + alias + "}", str(value))
    return rendered


def list_variables() -> list[dict]:
    return [item.view() for item in VARIABLES]
