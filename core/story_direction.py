"""Small story-only narrative controls; never alter adjudication or sampling."""

PREFERENCE_EMPHASIS = {
    "light": "轻度融入：优先作为自然细节，不主动把偏好扩展为新的剧情重心。",
    "balanced": "适中融入：有合适机会时自然展开，也保留其他主题，不逐回合重复强化。",
    "prominent": "突出融入：机会合适时可围绕偏好展开一段互动或情节，仍保留变化，不强行反复插入。",
}


def normalize_preference_emphasis(value):
    return value if isinstance(value, str) and value in PREFERENCE_EMPHASIS else "balanced"


def direction_context(direction: str) -> str:
    if not direction.strip():
        return ""
    return (
        "【剧情发展方向（玩家的创作期望，不是已经发生的事实）】\n"
        + direction.strip()
        + "\n在世界规则、人物立场与已裁定结果允许的空间内逐步靠近此方向；"
        "不要提前兑现未来目标，不据此赋予人物未知信息，也不代替玩家作下一重要选择。"
    )


def preference_emphasis_instruction(context: str, settings, *, future=False) -> str:
    if not context.strip():
        return ""
    level = normalize_preference_emphasis(settings.get("preferenceEmphasis"))
    scope = (
        "在可行方向的创作取材中参考偏好；喜欢不构成行动成功或事件必然发生的证据，不改硬条件。"
        if future else
        "只在已选结果内调整表达与关注重点，不重新选择未来或再次为偏好加权。"
    )
    return (
        "【本局偏好融入程度】" + PREFERENCE_EMPHASIS[level] + scope
        + "参考近期上下文避免重复；玩家本回合明确要求和仍在继续的场景不因低档位被打断，"
        "已有人物设定与世界事实不因档位变化而消失。这是软取向，不是固定出现频率。"
    )
