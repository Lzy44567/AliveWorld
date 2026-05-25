# app.py
import streamlit as st
import yaml, os
import traceback
from engine import AIEngine
import utils
import ui_tavern
from sys_logger import get_logger, read_logs_parsed

st.set_page_config(page_title="AliveWorld AI引擎", page_icon="🐉", layout="wide")
log = get_logger()

try:
    @st.cache_resource
    def init_core():
        with open(os.path.join(utils.BASE_DIR, 'config.yml'), 'r', encoding='utf-8') as f: 
            return AIEngine(yaml.safe_load(f))
    
    try: ai_engine = init_core()
    except Exception as e: st.error(f"配置加载失败: {e}"); st.stop()

    global_settings = utils.load_settings()

    if st.session_state.get('view_full_logs', False):
        st.markdown("""
        <style>
        .log-container { font-family: 'Consolas', monospace; color: #333; font-size: 13px; background-color: #f7f9fb; padding: 20px; border-radius: 8px; height: 75vh; overflow-y: auto; border: 1px solid #e1e4e8; box-shadow: inset 0 1px 3px rgba(0,0,0,.04); }
        .log-line { margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid #eee; }
        .log-time { color: #888; margin-right: 8px; }
        .log-module { color: #0366d6; font-weight: bold; margin-right: 8px; }
        .log-msg { color: #24292e; word-wrap: break-word; }
        </style>
        """, unsafe_allow_html=True)
        
        c1, c2 = st.columns([1, 10])
        if c1.button("⬅️ 返回游戏", use_container_width=True):
            st.session_state.view_full_logs = False
            st.rerun()
        c2.title("📊 系统日志历史 (最新在最上)")
        
        logs = read_logs_parsed()[::-1] 
        html_lines = []
        for l in logs:
            html_lines.append(f"<div class='log-line'><span class='log-time'>[{l['time']}]</span> <span>{l['icon']}</span> <span class='log-module'>[{l['module']}]</span> <span class='log-msg'>{l['message']}</span></div>")
        
        st.markdown(f"<div class='log-container'>{''.join(html_lines)}</div>", unsafe_allow_html=True)
        st.stop()

    if 'game_started' not in st.session_state or not st.session_state.game_started:
        ui_tavern.render_tavern(ai_engine, global_settings)
        st.stop()

    with st.sidebar:
        st.title("🛡️ 游戏状态")
        ps, deltas, bars, buffs = st.session_state.player_state, st.session_state.last_deltas, st.session_state.dynamic_bars, st.session_state.active_buffs
        
        st.metric("❤️ 生命", f"{ps['hp']} / {ps['max_hp']}", deltas['hp'])
        st.progress(max(0.0, min(ps['hp']/max(1,ps['max_hp']), 1.0)))
        st.metric("💧 灵力", f"{ps['mana']} / {ps['max_mana']}", deltas['mana'])
        st.progress(max(0.0, min(ps['mana']/max(1,ps['max_mana']), 1.0)))
        
        if bars:
            st.markdown("---")
            for bn, bd in bars.items():
                st.metric(f"💠 {bn}", f"{bd.get('current',0)} / {bd.get('max',1)}")
                st.progress(max(0.0, min(bd.get('current',0)/max(1,bd.get('max',1)), 1.0)))

        st.divider()
        st.markdown("### 📋 玩家状态")
        for k, v in st.session_state.player_properties.items(): st.info(f"**{k}:**\n{v}")

        if getattr(st.session_state, 'npc_states', None):
            st.divider()
            st.markdown("### 👾 场景 NPC 雷达")
            for k, v in st.session_state.npc_states.items(): st.error(f"**{k}**: {v}")
                
        if buffs:
            st.divider()
            st.markdown("### ⏳ 持续效果")
            for bn, bd in buffs.items():
                # 【修复】宽容取值防崩溃
                dur = '永久' if bd.get('duration', -1) == -1 else bd.get('duration', 0)
                hp_c = bd.get('hp_per_turn', 0)
                mp_c = bd.get('mana_per_turn', 0)
                eff = bd.get('effect', '无')
                st.warning(f"**{bn}** ({dur})\nHP: {hp_c} | MP: {mp_c}\n效果: {eff}")
        
        st.divider()
        with st.expander("⚙️ 引擎控制与存档", expanded=False):
            word_limit = st.slider("详细度 (字数)", 100, 2000, 500, 100)
            new_save_name = st.text_input("当前存档名", value=st.session_state.session_save_name)
            if new_save_name != st.session_state.session_save_name:
                st.session_state.session_save_name = new_save_name; utils.auto_save_game()
            if st.button("💾 手动保存", use_container_width=True): utils.auto_save_game(); st.toast("保存成功！")
            
            if st.button("📊 查看系统核心日志", type="primary", use_container_width=True):
                st.session_state.view_full_logs = True
                st.rerun()

    st.title("📖 AliveWorld")

    action = st.chat_input("轮到你了...")
    if getattr(st.session_state, 'trigger_retry', False):
        action = st.session_state.get('last_user_action', '继续推演')
        st.session_state.trigger_retry = False 
        st.toast("🔄 正在重新推演上一回合...", icon="🚀")

    is_processing_ai = False 

    if action and not st.session_state.game_over:
        st.session_state.last_user_action = action 
        utils.take_snapshot()
        st.session_state.chat_messages.append({"role": "user", "content": action})
        utils.auto_save_game()
        is_processing_ai = True 

    for msg in st.session_state.chat_messages:
        if msg["role"] == "user":
            with st.chat_message("user", avatar="🤔"): st.write(msg["content"])
        elif msg["role"] == "reactions":
            with st.chat_message("assistant", avatar="⚙️"):
                with st.expander("👁️ 命运观测器", expanded=False):
                    for r in msg["content"]: st.markdown(f"**路线 {r['id']} ({r['weight']}%):** {r['description']}")
        elif msg["role"] == "system":
            with st.chat_message("assistant", avatar="🎲"): st.caption(f"*{msg['content']}*")
        elif msg["role"] == "ai":
            with st.chat_message("assistant", avatar="🐉"): st.write(msg["content"])

    if st.session_state.game_over: st.error("☠️ 你已死亡。")

    if is_processing_ai:
        ctx = "\n".join(st.session_state.context_history[-3:])
        f_state = {"stats": st.session_state.player_state, "bars": st.session_state.dynamic_bars, "properties": st.session_state.player_properties, "buffs": st.session_state.active_buffs, "npcs": getattr(st.session_state, 'npc_states', {})}
        
        with st.chat_message("assistant", avatar="⚙️"):
            with st.spinner("🔍 检索世界记忆中..."):
                active_world_info, triggered = utils.build_active_world_info(ctx, action)
                if triggered: st.toast(f"📖 触发世界记忆: {', '.join(triggered)}")

            with st.spinner("🧠 推演因果律中..."):
                reactions, raw_react_json = ai_engine.get_world_reactions(ctx, action, f_state, st.session_state.char_info, active_world_info)
                
            if reactions:
                st.session_state.chat_messages.append({"role": "reactions", "content": reactions})
                with st.expander("👁️ 命运观测器", expanded=False):
                    for r in reactions: st.markdown(f"**路线 {r['id']} ({r['weight']}%):** {r['description']}")
                
                chosen = ai_engine.roll_dice(reactions)
                st.session_state.chat_messages.append({"role": "system", "content": f"命运变数: {chosen['description']}"})
                st.caption(f"*🎯 {chosen['description']}*")
                
                with st.spinner("✍️ 具现化世界线中..."):
                    result, raw_settle_json = ai_engine.generate_story_and_state(ctx, action, chosen, f_state, word_limit, st.session_state.char_info, st.session_state.style_info, active_world_info)
                    
                if result:
                    st.session_state.chat_messages.append({"role": "ai", "content": result.get('story_text', '生成异常，请检查Log')})
                    st.session_state.context_history.append(f"玩家：{action}\n结果：{result.get('story_text', '')}")
                    utils.apply_state_updates(result)
                    utils.auto_save_game() 
                    st.rerun() 
                else:
                    st.error("❌ 严重异常：结算结果为空，已记录至日志。")
                    is_processing_ai = False 
            else:
                st.error("❌ 推演阶段异常，无法生成变数，已记录至日志。")
                is_processing_ai = False 

    if not is_processing_ai and not st.session_state.game_over:
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            if st.button("⏪ 撤回上回合", use_container_width=True):
                if len(st.session_state.state_snapshots) > 0:
                    last_snap = st.session_state.state_snapshots.pop()
                    for k, v in last_snap.items(): st.session_state[k] = v
                    utils.auto_save_game(); st.rerun()
                else: st.toast("已经是第一回合！", icon="⚠️")
        with col2:
            if st.button("🔄 一键重试本回合", type="secondary", use_container_width=True):
                if len(st.session_state.state_snapshots) > 0:
                    fallback_action = "继续推演"
                    for msg in reversed(st.session_state.chat_messages):
                        if msg['role'] == 'user':
                            fallback_action = msg['content']
                            break
                    last_snap = st.session_state.state_snapshots.pop()
                    for k, v in last_snap.items(): st.session_state[k] = v
                    st.session_state.trigger_retry = True 
                    st.session_state.last_user_action = fallback_action
                    utils.auto_save_game()
                    st.rerun()
                else: st.toast("无记录可重试！", icon="⚠️")
        with col3:
            if st.button("🚪 返回大厅"): st.session_state.clear(); st.rerun()

except Exception as global_e:
    error_trace = traceback.format_exc()
    log.error(f"严重崩溃!\n{error_trace}", extra={'module_name': 'GlobalCatcher'})
    st.error("⚠️ 引擎遭遇严重逻辑错误！已被护盾拦截。")
    if st.button("🛠️ 进入抢修模式 (查看崩溃日志)"):
        st.session_state.view_full_logs = True
        st.rerun()