# app.py
import streamlit as st
import yaml, os, pandas as pd
from datetime import datetime
from utils.sys_logger import init_logger, get_logger, read_logs_parsed
from utils.file_io import load_settings, save_game_data, BASE_DIR
from core.ai_engine import AIEngine
from ui_tavern import render_tavern
from core.undercurrent import Entity
import streamlit.components.v1 as components

st.set_page_config(page_title="AliveWorld", page_icon="🐉", layout="wide")

@st.cache_resource
def init_system():
    log_name = os.path.join(BASE_DIR, 'logs', f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    init_logger(log_name)
    with open(os.path.join(BASE_DIR, 'config.yml'), 'r', encoding='utf-8') as f: 
        return AIEngine(yaml.safe_load(f))

ai_engine = init_system()
settings = load_settings()
log = get_logger()

# ================= 系统级终端日志 =================
if st.session_state.get('view_full_logs', False):
    c1, c2 = st.columns([1, 10])
    if c1.button("⬅️ 返回游戏"):
        st.session_state.view_full_logs = False
        st.rerun()
    c2.title("📊 系统终端日志 (黑客模式)")
    
    # 恢复正常的顺序（从旧到新），最底部是最新的
    logs = read_logs_parsed()
    html_lines = [f"<div style='margin-bottom:6px; border-bottom:1px solid #333; padding-bottom: 4px; font-family: Consolas, monospace; font-size: 13px; color: #d4d4d4;'>[{l['time']}] {l['icon']} <b style='color:#569cd6;'>[{l['module']}]</b> {l['message']}</div>" for l in logs]
    
    # 使用包含 JS 的完整 HTML 容器
    full_html = f"""
    <div id="log-container" style="background-color: #1e1e1e; padding: 20px; border-radius: 8px; height: 75vh; overflow-y: auto;">
        {''.join(html_lines)}
    </div>
    <script>
        var logBox = document.getElementById("log-container");
        logBox.scrollTop = logBox.scrollHeight;
    </script>
    """
    components.html(full_html, height=600, scrolling=False)
    st.stop()

if 'game' not in st.session_state:
    render_tavern(ai_engine, settings)
    st.stop()

game = st.session_state.game

# ================= 侧边栏 =================
with st.sidebar:
    st.title(f"🛡️ 冒险: {game.save_name}")
    ps, deltas = game.state['player'], game.state['last_deltas']
    
    st.metric("❤️ 生命", f"{ps['hp']} / {ps['max_hp']}", deltas['hp'])
    st.progress(max(0.0, min(ps['hp']/max(1,ps['max_hp']), 1.0)))
    st.metric("💧 灵力", f"{ps['mana']} / {ps['max_mana']}", deltas['mana'])
    st.progress(max(0.0, min(ps['mana']/max(1,ps['max_mana']), 1.0)))
    
    if game.state['bars']:
        st.markdown("---")
        for bn, bd in game.state['bars'].items():
            st.metric(f"💠 {bn}", f"{bd['current']}/{bd['max']}")
            st.progress(max(0.0, min(bd['current']/max(1,bd['max']), 1.0)))
    
    st.divider()
    for k, v in game.state['properties'].items(): st.info(f"**{k}:** {v}")
    if game.state['npcs']:
        st.divider()
        st.markdown("### 👾 NPC 雷达")
        for k, v in game.state['npcs'].items(): st.error(f"**{k}**: {v}")
        
    st.divider()
    st.markdown("### 🌌 世界实体观测窗")
    st.caption("你可以在此手动捏造势力或仇人。")
    
    ent_data = [{"名称": e.name, "动机": e.goal} for e in game.undercurrent.entities]
    if not ent_data: ent_data = [{"名称": "", "动机": ""}]
    
    df_ents = pd.DataFrame(ent_data)
    edited_df = st.data_editor(df_ents, num_rows="dynamic", use_container_width=True, hide_index=True)
    
    new_entities = []
    for _, row in edited_df.dropna(how="all").iterrows():
        if str(row.get("名称")).strip():
            new_entities.append(Entity(str(row["名称"]), str(row.get("动机", ""))))
    game.undercurrent.entities = new_entities
    
    st.divider()
    with st.expander("⚙️ 设置", expanded=False):
        game.word_limit = st.slider("详细度(字数)", 100, 2000, game.word_limit, 100)
        if st.button("💾 手动保存"):
            save_game_data(game.save_name, game.export_save_data())
            st.toast("保存成功！")
        if st.button("📊 查看系统核心日志"):
            st.session_state.view_full_logs = True
            st.rerun()
        if st.button("🚪 返回大厅"):
            del st.session_state.game
            st.rerun()

# ================= 主渲染循环 =================
st.title("📖 AliveWorld")

for msg in game.history['chat_messages']:
    role_icon = {"user": "🤔", "ai": "🐉", "system": "🎲", "reactions": "👁️"}.get(msg["role"], "📝")
    with st.chat_message(msg["role"] if msg["role"] in ["user", "ai"] else "assistant", avatar=role_icon):
        if msg["role"] == "reactions":
            with st.expander("命运观测器"):
                for r in msg["content"]: st.write(f"路线 {r['id']} ({r['weight']}%): {r['description']}")
        else:
            st.write(msg["content"])

if game.is_game_over: st.error("☠️ 你已死亡。")

action = st.chat_input("轮到你了...")
is_processing = False

if getattr(st.session_state, 'trigger_retry', False):
    action = st.session_state.last_action
    st.session_state.trigger_retry = False

if action and not game.is_game_over:
    st.session_state.last_action = action
    is_processing = True
    with st.chat_message("user", avatar="🤔"): st.write(action)
    with st.spinner("🧠 引擎推演中..."):
        result = game.process_turn(action)
        if result and result.get('triggered_entries'):
            st.toast(f"📖 触发世界记忆: {', '.join(result['triggered_entries'])}")
    save_game_data(game.save_name, game.export_save_data())
    st.rerun()

if not is_processing and not game.is_game_over:
    st.markdown("---")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("⏪ 撤回上回合", use_container_width=True):
            if game.rollback(): 
                save_game_data(game.save_name, game.export_save_data())
                st.rerun()
            else: st.toast("已经是第一回合！", icon="⚠️")
    with c2:
        if st.button("🔄 重试本回合", type="secondary", use_container_width=True):
            if game.rollback(): 
                st.session_state.trigger_retry = True
                st.rerun()
            else: st.toast("无记录可重试！", icon="⚠️")