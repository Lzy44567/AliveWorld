# app.py
import streamlit as st
import yaml, json, os, glob
from datetime import datetime
import pandas as pd
from engine import AIEngine
import utils 

st.set_page_config(page_title="AliveWorld AI引擎", page_icon="🐉", layout="wide")

@st.cache_resource
def init_core():
    with open(os.path.join(utils.BASE_DIR, 'config.yml'), 'r', encoding='utf-8') as f: return AIEngine(yaml.safe_load(f))
try: ai_engine = init_core()
except Exception as e: st.error(f"配置加载失败: {e}"); st.stop()

global_settings = utils.load_settings()

# ================= 大厅系统 =================
if 'game_started' not in st.session_state or not st.session_state.game_started:
    st.title("🏰 AliveWorld - 多元宇宙大厅")
    tab_lobby, tab_saves, tab_char, tab_world, tab_style = st.tabs(["🚀 开启新故事", "📂 记忆档案馆", "🗂️ 角色工坊", "🌍 世界书工坊", "🎭 文风工坊"])
    
    char_dict = utils.load_yaml_files(utils.CHAR_DIR)
    style_dict = utils.load_yaml_files(utils.STYLE_DIR)
    world_dict = utils.load_yaml_files(utils.WORLD_DIR)
    
    with tab_lobby:
        if not char_dict: st.warning("请先去【角色工坊】创建一张角色卡。")
        else:
            c1, c2, c3 = st.columns(3)
            sel_char_name = c1.selectbox("📝 选择化身", list(char_dict.keys()))
            style_options = ["默认 (无)"] + list(style_dict.keys())
            sel_style_name = c2.selectbox("🎭 选择文风", style_options, index=style_options.index(global_settings['default_style']) if global_settings['default_style'] in style_options else 0)
            sel_world_name = c3.selectbox("🌍 载入世界书", ["无界域 (暂不加载)"] + list(world_dict.keys()))
            
            sel_char = char_dict[sel_char_name]
            style_content = style_dict[sel_style_name]['content'] if sel_style_name != "默认 (无)" else "遵循常规逻辑推演。"
            world_data = world_dict[sel_world_name] if sel_world_name != "无界域 (暂不加载)" else {}
            
            world_base = world_data.get('global_setting', '无特定世界观。')
            final_opening = (world_data.get('starting_scene', '') + "\n\n" + sel_char.get('starting_scene', '')) if world_data.get('starting_scene', '') else sel_char.get('starting_scene', '')
            
            with st.container(border=True):
                st.markdown(f"**📖 角色设定:** {sel_char.get('description', '无')}")
                st.markdown(f"**🎬 最终开场白:** {final_opening[:100]}...")

            if st.button("🚀 链接新世界", type="primary", use_container_width=True):
                st.session_state.log_file = utils.setup_logger()
                st.session_state.char_info, st.session_state.style_info = sel_char.get('description', ''), style_content
                st.session_state.world_info_base, st.session_state.world_entries = world_base, world_data.get('entries', []) 
                hp, mana = sel_char.get('initial_hp', 100), sel_char.get('initial_mana', 100)
                st.session_state.player_state = {"hp": hp, "max_hp": hp, "mana": mana, "max_mana": mana}
                st.session_state.dynamic_bars, st.session_state.active_buffs, st.session_state.player_properties = {}, {}, {"身体": "完好", "衣服": "完好"}
                st.session_state.last_deltas = {"hp": 0, "max_hp": 0, "mana": 0, "max_mana": 0}
                st.session_state.chat_messages, st.session_state.context_history, st.session_state.state_snapshots = [{"role": "ai", "content": final_opening, "type": "story"}], [final_opening], []
                st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.session_state.session_save_name = f"{sel_char_name}_{st.session_state.session_id}"
                st.session_state.game_over, st.session_state.game_started = False, True
                utils.auto_save_game()
                st.rerun()

    with tab_saves:
        saves = {}
        for f in glob.glob(os.path.join(utils.SAVE_DIR, "*.json")):
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    data = json.load(file); data['_filepath'] = f; saves[data['save_name']] = data
            except: pass
        if not saves: st.info("当前没有任何存档。")
        else:
            sel_save_name = st.selectbox("📂 选择存档", list(saves.keys()))
            sel_save = saves[sel_save_name]
            c1, c2 = st.columns(2)
            if c1.button("📂 载入故事线", type="primary", use_container_width=True):
                st.session_state.log_file = utils.setup_logger()
                for k in ['char_info', 'style_info', 'world_info_base', 'world_entries', 'player_state', 'dynamic_bars', 'active_buffs', 'player_properties', 'last_deltas', 'chat_messages', 'context_history', 'state_snapshots']:
                    st.session_state[k] = sel_save.get(k, "" if k == 'world_info_base' else ([] if k in ['world_entries', 'state_snapshots'] else {}))
                st.session_state.session_id, st.session_state.session_save_name = datetime.now().strftime("%Y%m%d_%H%M%S"), sel_save_name
                st.session_state.game_over, st.session_state.game_started = False, True
                st.rerun()
            if c2.button("🗑️ 删除存档", type="secondary", use_container_width=True):
                os.remove(sel_save['_filepath'])
                st.rerun()

    with tab_char:
        mode = st.radio("模式", ["✨ 创建", "✏️ 编辑"], key="c_mode", horizontal=True)
        edit_target = char_dict[st.selectbox("选择", list(char_dict.keys()), key="c_sel")] if mode == "✏️ 编辑" and char_dict else None
        with st.form("char_form"):
            f_name = st.text_input("角色名", value=edit_target['name'] if edit_target else "")
            f_type = st.selectbox("类型", ["PC", "NPC"], index=0 if (not edit_target or edit_target.get('type')=='PC') else 1)
            c1, c2 = st.columns(2)
            f_hp = c1.number_input("HP", min_value=1, value=edit_target['initial_hp'] if edit_target else 100)
            f_mana = c2.number_input("MP", min_value=0, value=edit_target['initial_mana'] if edit_target else 100)
            f_desc = st.text_area("设定", value=edit_target['description'] if edit_target else "", height=100)
            f_scene = st.text_area("开场白", value=edit_target['starting_scene'] if edit_target else "", height=100)
            if st.form_submit_button("💾 保存卡片", type="primary") and f_name.strip():
                safe_fn = "".join(x for x in f_name if x.isalnum() or x in " _-")
                if edit_target and edit_target['name'] != f_name: os.remove(edit_target['_filepath'])
                with open(os.path.join(utils.CHAR_DIR, f"{safe_fn}.yml"), 'w', encoding='utf-8') as f:
                    yaml.dump({"name": f_name.strip(), "type": f_type, "initial_hp": f_hp, "initial_mana": f_mana, "description": f_desc, "starting_scene": f_scene}, f, allow_unicode=True)
                st.rerun()

    with tab_world:
        if 'ai_world_draft' not in st.session_state:
            st.session_state.ai_world_draft = None

        with st.expander("🧠 AI 世界架构师 (输入灵感，一键生成整个世界)"):
            world_idea = st.text_input("输入灵感（例：赛博修仙、高魔废土、克苏鲁大航海...）")
            if st.button("✨ 创造世界"):
                with st.spinner("神明正在构筑法则...这需要大约半分钟..."):
                    draft = ai_engine.generate_worldbook(world_idea)
                    if draft:
                        st.session_state.ai_world_draft = draft
                        st.success("世界创造成功！已自动填入下方表格，确认无误后请点击最下方保存。")
                    else:
                        st.error("生成失败，请重试。")

        wmode = st.radio("模式", ["✨ 创建新世界", "✏️ 编辑世界"], key="w_mode", horizontal=True)
        wedit_target = world_dict[st.selectbox("选择世界", list(world_dict.keys()), key="w_sel")] if wmode == "✏️ 编辑世界" and world_dict else None
        
        draft = st.session_state.ai_world_draft
        def_name = draft['name'] if draft else (wedit_target['name'] if wedit_target else "")
        def_global = draft['global_setting'] if draft else (wedit_target.get('global_setting', '') if wedit_target else "")
        def_open = draft['starting_scene'] if draft else (wedit_target.get('starting_scene', '') if wedit_target else "")
        def_entries = draft['entries'] if draft else (wedit_target.get('entries', [{"name": "范例", "keys": "关键字1", "content": "设定..."}]) if wedit_target else [{"name": "", "keys": "", "content": ""}])

        w_name = st.text_input("世界名称", value=def_name)
        w_global = st.text_area("常驻世界法则", value=def_global, height=100)
        w_open = st.text_area("世界开场白", value=def_open, height=100)
        
        df = pd.DataFrame(def_entries)
        st.markdown("##### 触发词条管理 (Data Editor)")
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True)
        
        if st.button("💾 保存世界书", type="primary") and w_name.strip():
            world_data = {"name": w_name.strip(), "global_setting": w_global, "starting_scene": w_open, "entries": edited_df.dropna(how="all").to_dict('records')}
            safe_fn = "".join(x for x in w_name if x.isalnum() or x in " _-")
            if wedit_target and wedit_target['name'] != w_name: os.remove(wedit_target['_filepath'])
            with open(os.path.join(utils.WORLD_DIR, f"{safe_fn}.yml"), 'w', encoding='utf-8') as f: 
                yaml.dump(world_data, f, allow_unicode=True)
            st.session_state.ai_world_draft = None # 清除草稿
            st.rerun()
            
    with tab_style:
        if 'ai_style_draft' not in st.session_state:
            st.session_state.ai_style_draft = ""

        with st.expander("🧙‍♂️ AI 文风大师 (输入几句话，AI帮你写出严谨的系统指令)"):
            short_prompt = st.text_input("你想要的文风（例：黑暗血腥、多视角描写、轻松网文）")
            if st.button("✨ 让 AI 构思文风"):
                with st.spinner("大师正在润色你的规则..."):
                    st.session_state.ai_style_draft = ai_engine.expand_style(short_prompt)

        smode = st.radio("模式", ["✨ 创建文风", "✏️ 编辑文风"], key="s_mode", horizontal=True)
        sedit_target = style_dict[st.selectbox("选择文风", list(style_dict.keys()), key="s_sel")] if smode == "✏️ 编辑文风" and style_dict else None
        
        with st.form("style_form"):
            s_name = st.text_input("文风名称", value=sedit_target['name'] if sedit_target else "")
            
            # 如果 AI 刚生成了草稿，则填入草稿；否则读取选中的卡片内容
            default_content = st.session_state.ai_style_draft if st.session_state.ai_style_draft else (sedit_target['content'] if sedit_target else "")
            s_content = st.text_area("文风约束 (Prompt指令)", value=default_content, height=150)
            
            if st.form_submit_button("💾 保存文风", type="primary") and s_name.strip():
                safe_fn = "".join(x for x in s_name if x.isalnum() or x in " _-")
                if sedit_target and sedit_target['name'] != s_name: os.remove(sedit_target['_filepath'])
                with open(os.path.join(utils.STYLE_DIR, f"{safe_fn}.yml"), 'w', encoding='utf-8') as f: 
                    yaml.dump({"name": s_name.strip(), "content": s_content}, f, allow_unicode=True)
                st.session_state.ai_style_draft = "" # 清空草稿
                st.rerun()
    st.stop()

# ================= 游戏主界面 =================
with st.sidebar:
    st.title("🛡️ 状态栏")
    word_limit = st.slider("详细度 (字数)", 100, 2000, 500, 100)
    
    new_save_name = st.text_input("当前存档", value=st.session_state.session_save_name)
    if new_save_name != st.session_state.session_save_name:
        st.session_state.session_save_name = new_save_name; utils.auto_save_game()
        
    c1, c2 = st.columns(2)
    if c1.button("💾 手动保存", use_container_width=True): utils.auto_save_game(); st.toast("保存成功！")
    if c2.button("⏪ 撤回", use_container_width=True):
        if len(st.session_state.state_snapshots) > 0:
            last_snap = st.session_state.state_snapshots.pop()
            for k, v in last_snap.items(): st.session_state[k] = v
            utils.auto_save_game(); st.rerun()

    st.divider()
    ps, deltas, bars, buffs = st.session_state.player_state, st.session_state.last_deltas, st.session_state.dynamic_bars, st.session_state.active_buffs
    cc1, cc2 = st.columns(2)
    cc1.metric("❤️ 生命", f"{ps['hp']}/{ps['max_hp']}", deltas['hp']); cc1.progress(max(0.0, min(ps['hp']/max(1,ps['max_hp']), 1.0)))
    cc2.metric("💧 灵力", f"{ps['mana']}/{ps['max_mana']}", deltas['mana']); cc2.progress(max(0.0, min(ps['mana']/max(1,ps['max_mana']), 1.0)))
    
    if bars:
        st.markdown("---")
        for bn, bd in bars.items():
            st.metric(f"💠 {bn}", f"{bd.get('current',0)}/{bd.get('max',1)}")
            st.progress(max(0.0, min(bd.get('current',0)/max(1,bd.get('max',1)), 1.0)))

    st.divider()
    st.markdown("### ⏳ 持续效果")
    for bn, bd in buffs.items(): st.warning(f"**{bn}** ({'永久' if bd['duration']==-1 else bd['duration']})\nHP:{bd['hp_per_turn']} | MP:{bd['mana_per_turn']}")

    st.divider()
    st.markdown("### 📋 状态")
    for k, v in st.session_state.player_properties.items(): st.info(f"**{k}:**\n{v}")
    
    if st.button("🚪 返回大厅", use_container_width=True): st.session_state.clear(); st.rerun()

st.title("📖 AliveWorld")

for msg in st.session_state.chat_messages:
    if msg["role"] == "user":
        with st.chat_message("user", avatar="🤔"): st.write(msg["content"])
    elif msg["role"] == "system":
        with st.chat_message("assistant", avatar="🎲"): st.caption(f"*{msg['content']}*")
    elif msg["role"] == "ai":
        with st.chat_message("assistant", avatar="🐉"): st.write(msg["content"])

if st.session_state.game_over: st.error("☠️ 你已死亡。")
else:
    action = st.chat_input("轮到你了...")
    if action:
        utils.take_snapshot()
        st.session_state.chat_messages.append({"role": "user", "content": action})
        
        utils.auto_save_game() 
        
        with st.chat_message("user", avatar="🤔"): st.write(action)
            
        ctx = "\n".join(st.session_state.context_history[-3:])
        f_state = {"stats": st.session_state.player_state, "bars": st.session_state.dynamic_bars, "properties": st.session_state.player_properties, "buffs": st.session_state.active_buffs}
        
        with st.chat_message("assistant", avatar="⚙️"):
            with st.spinner("🔍 检索世界记忆中..."):
                active_world_info, triggered = utils.build_active_world_info(ctx, action)
                if triggered: st.toast(f"📖 触发世界记忆: {', '.join(triggered)}")

            with st.spinner("🧠 推演因果律中..."):
                reactions = ai_engine.get_world_reactions(ctx, action, f_state, st.session_state.char_info, active_world_info)
                
            if reactions:
                with st.expander("👁️ 命运观测器", expanded=False):
                    for r in reactions: st.markdown(f"**路线 {r['id']} ({r['weight']}%):** {r['description']}")
                
                chosen = ai_engine.roll_dice(reactions)
                st.session_state.chat_messages.append({"role": "system", "content": f"命运变数: {chosen['description']}"})
                st.caption(f"*🎯 {chosen['description']}*")
                
                with st.spinner("✍️ 具现化世界线中..."):
                    result = ai_engine.generate_story_and_state(ctx, action, chosen, f_state, word_limit, st.session_state.char_info, st.session_state.style_info, active_world_info)
                    
                if result:
                    st.session_state.chat_messages.append({"role": "ai", "content": result.get('story_text', '...')})
                    st.session_state.context_history.append(f"玩家：{action}\n结果：{result.get('story_text', '...')}")
                    utils.apply_state_updates(result)
                    
                    utils.auto_save_game() 
                    st.rerun()