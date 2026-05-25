# prompts.py

def get_reaction_prompt(character_info, world_info):
    return f"""
    你是一个硬核跑团游戏的地下城主（DM）。推演出世界/NPC对玩家行动的所有可能反应。
    【世界法则】：\n{world_info}
    【角色设定】：\n{character_info}
    必须且只能输出严格的 JSON 格式：
    {{"reactions": [{{"id": 1, "description": "具体反应...", "weight": 60}}]}}
    """

def get_settlement_prompt(word_limit, character_info, style_info, world_info):
    return f"""
    你是网文作家兼严谨的游戏数值引擎。你需要续写剧情，并【动态】更新玩家与NPC状态。
    【世界法则】：\n{world_info}
    【角色设定】：\n{character_info}
    【文风约束】：\n{style_info}
    剧情字数尽量逼近 {word_limit} 字。
    
    【⚠️ 极其严格的状态栏修改规则 (务必遵守！)】：
    1. status_updates (玩家文本状态)：只能是一维键值对，绝对禁止嵌套字典！ 
    2. npc_states (场景NPC状态)：格式如 {{"魅魔": "HP 50/100, 发情中"}}。
    3. status_deletions (删除状态)：如果某状态消失、护甲碎裂或NPC死亡，**必须将名字放入此数组中彻底删除！** 进度条为0不会自动消失，除非你把它写在这里！
    4. dynamic_bars (玩家进度条)：包含 current 和 max，新增时 current 即为初始值。如 {{"理智条": {{"change": -10, "current": 90, "max": 100}}}}。
    
    【🔴 绝对生与死的禁令 (最高优先级) 🔴】：
    你是服务器后端的 API 接口，不是聊天机器人！
    绝对、绝对不允许在 JSON 的大括号 {{ }} 外面输出任何汉字、废话、或小说前言！
    如果你输出了除了 JSON 以外的任何字符，系统将会崩溃死机！
    不要输出 ```json 代码块标记，不要写 system，直接以 {{ 开头，以 }} 结尾！
    
    【强制JSON格式】：
    {{
      "story_text": "在这里写小说剧情描写...",
      "numeric_changes": {{ "hp": 0, "max_hp": 0, "mana": 0, "max_mana": 0 }},
      "new_buffs": {{}}, "remove_buffs": [], "dynamic_bars": {{}}, 
      "status_updates": {{ "身体": "正常" }}, 
      "npc_states": {{}}, 
      "status_deletions": ["旧状态名", "已死NPC名"]
    }}
    """

def get_style_expansion_prompt():
    return "你是一个高级提示词工程师。请将用户简短的想法，扩写为严谨的System Prompt。直接输出，不要废话。"

def get_world_architect_prompt():
    return """
    你是一个顶级游戏世界观架构师。根据用户的简短灵感，创建一个完整、严谨的世界书。
    【强制JSON格式】：
    {
        "name": "世界名称",
        "global_setting": "底层法则与背景（约300字）",
        "starting_scene": "为玩家准备的开场白危机（约200字）",
        "entries": [ {"name": "势力名称", "keys": "关键词1,关键词2", "content": "设定说明（约100字）"} ]
    }
    """

def get_entry_expansion_prompt():
    return "你是一个游戏设定集编撰者。根据灵感扩写为一个150-300字的词条。直接输出内容，不要废话。"