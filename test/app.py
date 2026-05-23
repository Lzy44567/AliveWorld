# app.py
import streamlit as st
import yaml
import os
import logging
from datetime import datetime
from engine import AIEngine
import utils  # 📥 导入写好的中枢工具模块，激活高级底层支持

st.set_page_config(page_title="AliveWorld AI引擎", page_icon="🐉", layout="wide")

# ================= 初始化系统 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
utils.setup_logger()  # 🛠️ 统一调用 utils 中的硬核日志初始化

@st.cache_resource
def init_core():
    config_path = os.path.join(BASE_DIR, 'config.yml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return AIEngine(config)

engine = init_core()

# 核心 Session State 状态树初始化
if "history" not in st.session_state:
    st.session_state.history = []
if "player_stats" not in st.session_state:
    st.session_state.player_stats = {"hp": 100, "max_hp": 100, "mana": 50, "max_mana": 50}
if "active_buffs" not in st.session_state:
    st.session_state.active_buffs = {}
if "dynamic_bars" not in st.session_state:
    st.session_state.dynamic_bars = {}
if "status_updates" not in st.session_state:
    st.session_state.status_updates = {}
if "pending_reactions" not in st.session_state:
    st.session_state.pending_reactions = None
if "current_action" not in st.session_state:
    st.session_state.current_action = ""
if "world_intro_done" not in st.session_state:
    st.session_state.world_intro_done = False

# ================= 🧭 侧边栏：模块中枢 (Tavern) 与状态面板 =================
st.sidebar.title("🐉 AliveWorld 控制台")

# 1. 存档/读档系统对接
st.sidebar.subheader("💾 编年史时间线")
col_save, col_load = st.sidebar.columns(2)

# 动态获取历史存盘文件
try:
    saves = utils.list_saves()
except AttributeError:
    saves = []
selected_save = st.sidebar.selectbox("读取历史时间线", ["新冒险开头"] + saves)

if col_save.button("保存当前因果", use_container_width=True):
    save_name = f"save_{datetime.now().strftime('%m%d_%H%M%S')}"
    current_state = {
        "history": st.session_state.history,
        "player_stats": st.session_state.player_stats,
        "active_buffs": st.session_state.active_buffs,
        "dynamic_bars": st.session_state.dynamic_bars,
        "status_updates": st.session_state.status_updates,
        "world_intro_done": st.session_state.world_intro_done
    }
    try:
        utils.save_game(save_name, current_state)
        st.sidebar.success(f"💾 成功固化时间线: {save_name}")
    except AttributeError:
        st.sidebar.warning("utils.py 中 save_game 未完全就绪")

# 2. 酒馆模块配置解耦（世界书/角色卡/文风卡管理）
st.sidebar.subheader("🍺 酒馆模块配置")
try:
    characters = utils.list_characters()
    worldbooks = utils.list_worldbooks()
    styles = utils.list_styles()
except AttributeError:
    # 容错降级默认值
    characters, worldbooks, styles = ["默认主角"], ["未分类世界观"], ["默认文风"]

sel_char = st.sidebar.selectbox("🧙 角色模组卡", characters)
sel_world = st.sidebar.selectbox("🗺️ 宏观世界书", worldbooks)
sel_style = st.sidebar.selectbox("✍️ 文风叙事卡", styles)

# 3. 数值与 Tick 引擎看板
st.sidebar.subheader("📊 数值内核状态栏")
ps = st.session_state.player_stats

# 基础属性条
st.sidebar.progress(max(0.0, min(1.0, ps['hp']/max(1, ps['max_hp']))), text=f"❤️ 生命值: {ps['hp']}/{ps['max_hp']}")
st.sidebar.progress(max(0.0, min(1.0, ps['mana']/max(1, ps['max_mana']))), text=f"🧪 法力值: {ps['mana']}/{ps['max_mana']}")

# 动态属性扩展条 (如护盾、理智值、怒气等)
if st.session_state.dynamic_bars:
    for bar_name, bar_data in list(st.session_state.dynamic_bars.items()):
        curr = bar_data.get("current", 0)
        m_val = bar_data.get("max", 100)
        st.sidebar.progress(max(0.0, min(1.0, curr/max(1, m_val))), text=f"⚡ {bar_name}: {curr}/{m_val}")

# 挂载的持续 Buff 监控
if st.session_state.active_buffs:
    st.sidebar.caption("⏳ 正在生效的持续 Buff/环境状态:")
    for b_name, b_data in st.session_state.active_buffs.items():
        dur = b_data.get('duration', 0)
        dur_str = f"{dur} 回合" if dur > 0 else "永久"
        st.sidebar.info(f"**[{b_name}]** ({dur_str}): {b_data.get('desc', '')}")


# ================= 🎬 主界面：剧情流与命运推演 =================
st.title("🌍 命运推演主视窗")

# 💡 阶段四：开场白逻辑重构（世界设定优先，角色设定跟进）
if not st.session_state.world_intro_done:
    if st.button("🗺️ 唤醒世界线：加载常驻世界设定并生成序章", type="primary"):
        with st.spinner("正在扫描世界书并凝聚最初的因果..."):
            world_context = ""
            try:
                world_data = utils.load_worldbook(sel_world)
                world_context = world_data.get("constant_lore", "一片处于混沌之中的未知大陆。")
                char_data = utils.load_character(sel_char)
                char_intro = char_data.get("intro", "你迈出了属于自己的第一步。")
            except:
                world_context = "这是一个充满未知与变数的庞大世界。"
                char_intro = "你的冒险从此开始。"
            
            # 调用 AI 引擎结合世界书生成宏大的开场叙事
            dummy_reaction = {"description": "世界的法则重新开始运转。"}
            dynamic_state = {"player_stats": st.session_state.player_stats, "active_buffs": st.session_state.active_buffs, "dynamic_bars": st.session_state.dynamic_bars}
            
            try:
                story_res = engine.generate_story_and_state(world_context, "降临", dummy_reaction, dynamic_state, word_limit=400)
                if story_res and 'story' in story_res:
                    st.session_state.history.append({"role": "assistant", "content": story_res['story']})
                    st.session_state.world_intro_done = True
                    st.rerun()
            except Exception as e:
                st.error(f"序章唤醒失败: {e}")

# 实时渲染编年史文本流
for msg in st.session_state.history:
    if msg["role"] == "user":
        st.chat_message("user", avatar="👤").write(msg["content"])
    else:
        st.chat_message("assistant", avatar="🐉").write(msg["content"])


# ================= 👁️ 核心：命运干涉系统 (Lore & Control) =================
st.divider()

# 实时构建当前的动态上下文（抓取近几轮对话作为短期记忆输入）
recent_context = "\n".join([f"{'玩家' if m['role']=='user' else '世界'}: {m['content']}" for m in st.session_state.history[-6:]])

# 🧠 阶段四：动态词条扫描 (扫描最近上下文，触发命中关键词的世界书词条并注入)
active_lore = ""
try:
    active_lore = utils.build_active_world_info(recent_context, sel_world)
except AttributeError:
    pass

full_context = f"{active_lore}\n{recent_context}"

# 接收玩家输入行动
with st.container():
    player_action = st.chat_input("输入你接下来的举动（例如：低声咏唱咒语，向地底通道投掷一枚照明光球...）")
    
    if player_action:
        st.session_state.current_action = player_action
        # 第一轨：AI 命运发散
        with st.spinner("🔮 正在观测未来的无限因果分支..."):
            dynamic_state = {"player_stats": st.session_state.player_stats, "active_buffs": st.session_state.active_buffs, "dynamic_bars": st.session_state.dynamic_bars}
            reactions = engine.get_world_reactions(full_context, player_action, dynamic_state)
            st.session_state.pending_reactions = reactions
            st.rerun()

# 当发散结果出来后，拦截并渲染【命运观测与手动干涉器】
if st.session_state.pending_reactions:
    st.markdown("### 👁️ 命运观测器 (Destiny Observer)")
    st.info(f"**玩家意图产生的行动：** {st.session_state.current_action}")
    st.caption("✨ **命运干涉系统激活**：你可以直接修改下方文本框的内容来改变未来，并点击按钮将其‘强行锁定’；或者交由概率进行掷骰。")
    
    reactions_list = st.session_state.pending_reactions
    
    # 动态渲染分支，并赋予完全的编辑、锁定权限
    for idx, react in enumerate(reactions_list):
        col_desc, col_action = st.columns([8, 2])
        
        # 命运手动编辑区
        edited_desc = col_desc.text_area(
            f"因果线 #{react.get('id', idx+1)} (自然发生概率: {react.get('weight', 0)}%)", 
            value=react.get('description', ''),
            key=f"react_edit_{idx}"
        )
        react['description'] = edited_desc  # 绑定编辑同步
        
        # 命运强制锁定锁
        if col_action.button("✨ 强行降临此命运", key=f"force_{idx}", use_container_width=True):
            st.session_state.chosen_reaction = react
            
    st.write("---")
    # 传统的第二轨：Python 概率掷骰
    if st.button("🎲 顺应天命（根据权重随机掷骰）", type="primary", use_container_width=True):
        st.session_state.chosen_reaction = engine.roll_dice(reactions_list)

    # 最终决算阶段：AI 故事生成 + Python 状态自动修正
    if "chosen_reaction" in st.session_state and st.session_state.chosen_reaction:
        chosen = st.session_state.chosen_reaction
        action_text = st.session_state.current_action
        
        with st.spinner("🎬 正在扭转时空因果并同步数值引擎..."):
            dynamic_state = {"player_stats": st.session_state.player_stats, "active_buffs": st.session_state.active_buffs, "dynamic_bars": st.session_state.dynamic_bars}
            
            # 第三、四轨：大模型结合确定的命运分支生成宏大剧情与更新包
            settlement_res = engine.generate_story_and_state(full_context, action_text, chosen, dynamic_state, word_limit=500)
            
            if settlement_res:
                # 将本轮历史追加入编年史
                st.session_state.history.append({"role": "user", "content": action_text})
                st.session_state.history.append({"role": "assistant", "content": settlement_res.get('story', '')})
                
                # 🛠️ 核心接线：交由 utils.py 的解耦数值引擎去刷新 Buff 衰减、扣除及新状态挂载
                try:
                    utils.apply_state_updates(settlement_res)
                except AttributeError:
                    # 极其安全的双重容错降级降落伞
                    deltas = settlement_res.get('player_stats_deltas', {})
                    ps = st.session_state.player_stats
                    ps['max_hp'] += deltas.get('max_hp', 0)
                    ps['max_mana'] += deltas.get('max_mana', 0)
                    ps['hp'] = max(0, min(ps['hp'] + deltas.get('hp', 0), ps['max_hp']))
                    ps['mana'] = max(0, min(ps['mana'] + deltas.get('mana', 0), ps['max_mana']))
                
                # 💾 触发中枢自动持久化存档
                try:
                    current_state = {
                        "history": st.session_state.history,
                        "player_stats": st.session_state.player_stats,
                        "active_buffs": st.session_state.active_buffs,
                        "dynamic_bars": st.session_state.dynamic_bars,
                        "status_updates": st.session_state.status_updates,
                        "world_intro_done": st.session_state.world_intro_done
                    }
                    utils.auto_save_game(current_state)
                except AttributeError:
                    pass
                
                # 清洗临时期会话状态，闭环当前 Tick，完美进入下一轮推演
                st.session_state.pending_reactions = None
                st.session_state.current_action = ""
                st.session_state.chosen_reaction = None
                st.rerun()