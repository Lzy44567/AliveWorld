"""LLM prompt engineering kept separate from image provider execution."""

from __future__ import annotations

import json
from typing import Any

from core.ai_engine import robust_json_parse


PROMPT_COMPILER_SYSTEM = """你是 AliveWorld 的生图提示词编译器。你只把已经给出的故事画面与玩家要求整理为生图模型更易理解的提示词，不续写剧情、不新增世界设定，也不决定是否应该生图。

规则：
1. 内容尺度由故事正文、角色资料和玩家要求共同决定，不另设“是否 R18”开关。不要擅自把普通场景色情化，也不要擅自净化正文已经明确的成人内容。
2. 普通画面重点描述主体、构图、动作、表情、服装、环境、光线和画风；成人画面除上述内容外，还应准确描述正文已经明确的身体状态、亲密动作、遮挡程度和镜头重点，但不得编造正文不存在的参与者或行为。
3. presentation_level 是玩家希望的表现尺度，例如保守、唯美、擦边、若隐若现、露点或更明确；它只能调整表现方式，不能推翻正文事实。
4. style_preference 是画风偏好。不要把文风卡中的文学修辞原样当成绘画标签，要转译成视觉特征。
5. positive 和 negative 优先使用简洁、无冲突的英文提示词，专有名词可保留；不要输出权重总和、解释性长文或 Markdown。
6. 图片类型为 character_portrait 时，你必须按“可长期复用的角色立绘”处理：突出单一角色稳定的脸部、发型、体型、服装和识别特征，采用完整或半身站姿、清楚轮廓与简洁背景；不要把正文中的一次性动作或临时伤势擅自固化为角色身份。
7. 图片类型为 character_cg 时，突出角色在当前剧情中的动作、表情、互动和场景；scene_cg 则优先还原事件构图、环境和在场主体。
8. model_name 是当前生图模型文件名，model_profile 是玩家为该模型填写的特性说明。仅在说明明确时适配其标签习惯；不要仅凭文件名编造模型能力。
9. 只使用玩家已经可见的正文、角色资料与世界书约束；暗流实体、因果账本、幕后计划等隐藏信息不得进入画面或提示词。
10. narrative_style_context 是启用文风卡的写作要求。只提取能够视觉化的倾向，例如色调、氛围、光影、镜头感、题材审美和内容侧重；忽略人称、字数、换行、对话格式、段落节奏等纯文学规则，不得把文风卡原文照抄进生图标签。
11. 玩家本次要求和 image style_preference 的优先级高于文风卡。角色立绘只弱参考文风的视觉气质，不能把临时叙事氛围固化为角色外观；剧情 CG 和场景 CG 可以更明显地转译文风。

严格输出 JSON：
{
  "positive": "最终正面提示词",
  "negative": "最终负面提示词",
  "content_focus": "general|sensual|explicit",
  "notes": "给玩家看的简短说明，指出保留了哪些关键画面事实"
}
"""


class PromptCompilationError(ValueError):
    pass


class ImagePromptCompiler:
    def __init__(self, ai_engine):
        self.ai_engine = ai_engine

    def compile(self, payload: dict[str, Any]) -> dict[str, str]:
        if not self.ai_engine:
            raise PromptCompilationError("未配置可用的大语言模型")
        user_prompt = (
            f"【图片类型】\n{payload.get('intent', 'scene_cg')}\n"
            f"【玩家要求】\n{payload.get('user_request', '')}\n"
            f"【对应正文】\n{payload.get('story_text', '')}\n"
            f"【角色资料】\n{payload.get('character_context', '')}\n"
            f"【世界与场景约束】\n{payload.get('world_context', '')}\n"
            f"【画风偏好】\n{payload.get('style_preference', '')}\n"
            f"【启用文风卡（仅提取可视觉化倾向）】\n{payload.get('narrative_style_context', '')}\n"
            f"【表现尺度】\n{payload.get('presentation_level', '')}"
            f"\n【生图模型】\n{payload.get('model_name', '')}"
            f"\n【模型特性说明】\n{payload.get('model_profile', '')}"
        )
        raw, error = self.ai_engine.chat_json(
            PROMPT_COMPILER_SYSTEM,
            user_prompt,
            temp=0.35,
            trace_label="生图提示词编译",
        )
        if error or not raw:
            raise PromptCompilationError(error or "提示词模型返回为空")
        try:
            result = robust_json_parse(raw)
        except ValueError as exc:
            raise PromptCompilationError(f"提示词模型返回的 JSON 无效: {exc}") from exc
        positive = str(result.get("positive", "")).strip()
        if not positive:
            raise PromptCompilationError("提示词模型没有返回正面提示词")
        focus = str(result.get("content_focus", "general")).strip()
        if focus not in {"general", "sensual", "explicit"}:
            focus = "general"
        return {
            "positive": positive,
            "negative": str(result.get("negative", "")).strip(),
            "content_focus": focus,
            "notes": str(result.get("notes", "")).strip(),
        }
