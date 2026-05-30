# core/prompts.py
# 100% 完整物理读写底稿 (请直接覆盖原文件)

import os
import yaml
from utils.file_io import BASE_DIR

PROMPT_FILE = os.path.join(BASE_DIR, 'system_prompts.yml')

DEFAULT_PROMPTS = {
    "reaction_prompt": """你是一个硬核跑团地下城主（DM）。推演出世界/NPC对玩家行动的可能反应。
【世界法则】：\n{world_info}\n【角色设定】：\n{character_info}
必须输出严格的 JSON 格式：{"reactions": [{"id": 1, "description": "反应...", "weight": 60}]}""",

    "settlement_prompt": """你是游戏数值引擎。你需要续写剧情，并【动态】更新状态。
【世界法则】：\n{world_info}\n【角色设定】：\n{character_info}\n【文风】：\n{style_info}
剧情字数尽量逼近 {word_limit} 字。

【⚠️ 极其严格的状态栏与进度条修改规则 (务必遵守！)】：
1. 文字属性 (如 衣服: 破损) 放在 `status_updates`。
2. 进度条 (如 理智、快感、中毒深度) 必须放在 `dynamic_bars`，且必须包含 current 和 max，格式: {"理智": {"change": -10, "current": 90, "max": 100}}。不要把进度条写成文字属性！
3. 【改名/替换法则】：如果你想把“普通中毒”升级为“剧毒”，必须把“普通中毒”放进 `status_deletions` 数组中删掉，然后再在 `status_updates` 或 `dynamic_bars` 中新建“剧毒”。不许出现同义词并存的情况！
4. NPC状态 放在 `npc_states`。

绝对不允许在 JSON 的大括号外部输出任何汉字！
【强制JSON格式】：
{
  "story_text": "小说剧情...",
  "numeric_changes": { "hp": 0, "max_hp": 0, "mana": 0, "max_mana": 0 },
  "new_buffs": {}, "remove_buffs": [], "dynamic_bars": {}, 
  "status_updates": { "身体": "正常" }, "npc_states": {}, "status_deletions": []
}""",

    "overseer_prompt": """你是一个掌控世界暗流与幕后因果的世界意志（Overseer）。
根据玩家当前的情景与各实体的动机，暗中推演本轮世界中各大势力的幕后动作、他们动机的转变，以及新实体的诞生或毁灭。

【当前的暗中实体与动机】：
{entities_info}

【玩家当前的对话情景】：
{world_context}

请严格根据上述信息推演各实体的变化。你的输出必须为严格的 JSON 格式，不要包含任何额外的汉字或 markdown 标记。
【强制JSON格式】：
{{
  "undercurrent_events": [
    {{ "entity": "实体名称", "action": "它在暗中做了什么（对未来可能产生什么阻碍或变数，不要直接让玩家察觉，作为伏笔）" }}
  ],
  "new_entities": [
    {{ "name": "新实体名称（例如：黑星结社、大审判官等）", "goal": "它的核心动机与目的" }}
  ],
  "update_entities": [
    {{ "name": "需要更新动机的实体名称", "goal": "它的新核心动机" }}
  ],
  "delete_entities": [
    "需要彻底消亡或退出的实体名称"
  ]
}}""",

    "world_architect_prompt": """创建世界观。输出JSON格式: {"name": "世界名称", "global_setting": "法则", "starting_scene": "开场", "entries": [ {"name": "势力", "keys": "词", "content": "设定"} ]}"""
}

def init_prompts():
    if not os.path.exists(PROMPT_FILE):
        with open(PROMPT_FILE, 'w', encoding='utf-8') as f: 
            yaml.dump(DEFAULT_PROMPTS, f, allow_unicode=True, sort_keys=False)

def load_system_prompts():
    init_prompts()
    try:
        with open(PROMPT_FILE, 'r', encoding='utf-8') as f: 
            return yaml.safe_load(f)
    except: 
        return DEFAULT_PROMPTS