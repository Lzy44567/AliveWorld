import json
import random
import yaml
import os
import logging
from datetime import datetime
from openai import OpenAI

# ================= 0. 初始化动态日志系统 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True) # 如果没有logs文件夹，自动创建一个

# 按时间生成本次运行的专属日志文件
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = os.path.join(LOG_DIR, f"game_run_{current_time}.log")

logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

# ================= 1. 读取配置与初始化 =================
config_path = os.path.join(BASE_DIR, 'config.yml')
try:
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    print(f"❌ 找不到配置文件：{config_path}")
    input("按回车键退出...")
    exit()

client = OpenAI(api_key=config['api_key'], base_url=config['base_url'])
MODEL_NAME = config['model']

# ================= 2. 核心逻辑函数 =================

def get_world_reactions(context, player_action, player_state):
    """阶段A：推演NPC和世界的反应"""
    system_prompt = """
    你是一个硬核跑团游戏的地下城主（DM）。
    根据当前情景、玩家当前状态和【玩家的行动】，推演出世界/NPC的所有可能反应，并分配贝叶斯概率权重（整数）。
    必须且只能输出严格的 JSON 格式：
    {"reactions": [{"id": 1, "description": "具体反应...", "weight": 60}]}
    """
    
    prompt = f"【当前情景/近期历史】：\n{context}\n【玩家当前状态】：{player_state}\n【玩家的行动】：{player_action}"
    print("\n🧠 正在推演世界的反应...")
    logging.info(f"玩家行动: {player_action}")
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        raw_response = response.choices[0].message.content
        logging.info(f"AI推演JSON: {raw_response}")
        return json.loads(raw_response)['reactions']
    except Exception as e:
        logging.error(f"推演失败: {e}")
        return None

def roll_dice(reactions):
    """阶段B：命运的骰子"""
    if not reactions: return None
    weights = [p['weight'] for p in reactions]
    chosen = random.choices(reactions, weights=weights, k=1)[0]
    print(f"🎯 命运变数：{chosen['description']}")
    return chosen

def generate_story_and_state(context, player_action, chosen_reaction, player_state):
    """阶段C：闭环写小说与结算"""
    system_prompt = """
    你是一个顶级网文作家兼严谨的游戏数值结算引擎。
    根据【前情提要】、【玩家行动】和【发生的变数】，续写一小段剧情（约200-300字）。
    并根据剧情，结算对玩家状态的影响。
    
    【强制JSON输出格式】：
    {
      "story_text": "剧情内容...",
      "status_update": {
        "hp_change": -10, // 增减数值，无变化填0
        "mana_change": -5, // 增减数值，无变化填0
        "body_status": "新状态（如：左臂骨折/完好/轻微中毒）",
        "clothes_status": "新状态（如：衣衫破烂/完好）"
      }
    }
    """
    prompt = f"【前情提要】：{context}\n【玩家当前状态】：{player_state}\n【玩家行动】：{player_action}\n【发生的变数】：{chosen_reaction['description']}"
    print("✍️ 正在生成剧情与结算状态...")
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            response_format={"type": "json_object"}
        )
        raw_response = response.choices[0].message.content
        logging.info(f"AI结算JSON: {raw_response}")
        return json.loads(raw_response)
    except Exception as e:
        logging.error(f"生成剧情失败: {e}")
        return None

# ================= 3. 游戏主循环 =================
if __name__ == "__main__":
    print(f"✅ 日志已自动保存在: {log_filename}")
    
    # 玩家初始状态（数据化）
    player_state = {
        "hp": 100,
        "max_hp": 100,
        "mana": 50,
        "max_mana": 100,
        "body_status": "完好",
        "clothes_status": "完好"
    }
    
    # 初始背景设定
    base_setting = "玩家角色（练气期五层，修炼冰系功法）进入了极热之地的‘赤炎沙漠’寻找火灵石。一队手持淬毒弯刀的沙匪包围了你。"
    
    # 游戏历史记录（短期记忆，防止下一次对话AI忘记前面的事）
    story_history = [base_setting]
    
    print("\n================== 游戏开始 ==================")
    print(f"📖 初始情景:\n{base_setting}\n")
    
    # 开启无限循环！
    while True:
        # 显示当前状态
        print(f"💖 当前状态 | HP: {player_state['hp']}/{player_state['max_hp']} | 灵力: {player_state['mana']}/{player_state['max_mana']} | 身体: {player_state['body_status']} | 衣服: {player_state['clothes_status']}")
        
        # 接收玩家输入
        player_action = input("\n🤔 轮到你了 (输入 '退出' 或 'quit' 结束游戏)\n>> ")
        
        if player_action.lower() in ['退出', 'quit']:
            print("游戏结束，感谢游玩！")
            break
            
        if not player_action.strip():
            continue
            
        # 拼接最近的上下文发给AI（保留最近的3条记录，防止文字太多超出AI限制）
        current_context = "\n".join(story_history[-3:]) 
        
        # 跑团三步曲
        reactions = get_world_reactions(current_context, player_action, player_state)
        if not reactions:
            continue
            
        chosen_reaction = roll_dice(reactions)
        
        result = generate_story_and_state(current_context, player_action, chosen_reaction, player_state)
        
        if result:
            print("\n================== 剧情发展 ==================\n")
            story_text = result['story_text']
            print(story_text)
            
            # --- 更新玩家真实状态！ ---
            updates = result.get('status_update', {})
            player_state['hp'] += updates.get('hp_change', 0)
            player_state['mana'] += updates.get('mana_change', 0)
            player_state['body_status'] = updates.get('body_status', player_state['body_status'])
            player_state['clothes_status'] = updates.get('clothes_status', player_state['clothes_status'])
            
            # 防止血量和蓝量溢出或低于0
            player_state['hp'] = max(0, min(player_state['hp'], player_state['max_hp']))
            player_state['mana'] = max(0, min(player_state['mana'], player_state['max_mana']))
            
            # 将本次发生的故事加入历史记录
            story_history.append(f"玩家行动：{player_action}\n结果：{story_text}")
            
            print("\n==============================================")
            
            # 死亡判定
            if player_state['hp'] <= 0:
                print("☠️ 你的HP已归零，你死在了赤炎沙漠...")
                print("游戏结束 (Game Over)")
                input("\n按回车键退出...")
                break