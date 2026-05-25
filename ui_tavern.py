# ui_tavern.py
import streamlit as st
import os, yaml, json, glob
import pandas as pd
from datetime import datetime
import utils
from sys_logger import get_logger

log = get_logger()

def render_tavern(ai_engine, global_settings):
    st.title("🏰 AliveWorld - 多元宇宙大厅")
    # 【新增】：第六个 Tab 引擎控制台
    tab_lobby, tab_saves, tab_char, tab_world, tab_style, tab_prompts = st.tabs(["🚀 开启新故事", "📂 记忆档案馆", "🗂️ 角色工坊", "🌍 世界书工坊", "🎭 文风工坊", "⚙️ 引擎控制台"])
    
    char_dict = utils.load_yaml_files(utils.CHAR_DIR)
    style_dict = utils.load_yaml_files(utils.STYLE_DIR)
    world_dict = utils.load_yaml_files(utils.WORLD_DIR)
    
    with tab_lobby:
        if not char_dict: st.warning("请先去【角色工坊】创建一张角色卡。")
        else:
            save_name_input = st.text_input("📝 为本次冒险命名 (必填)", value="")
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

            if st.button("🚀 链接新世界", type="primary", use_container_width=True, disabled=not save_name_input.strip()):
                log.info(f"玩家载入新世界: {save_name_input}", extra={'module_name': '多元宇宙大厅'})
                st.session_state.char_info, st.session_state.style_info = sel_char.get('description', ''), style_content
                st.session_state.world_info_base, st.session_state.world_entries = world_base, world_data.get('entries', []) 
                hp, mana = sel_char.get('initial_hp', 100), sel_char.get('initial_mana', 100)
                st.session_state.player_state = {"hp": hp, "max_hp": hp, "mana": mana, "max_mana": mana}
                st.session_state.dynamic_bars, st.session_state.active_buffs, st.session_state.player_properties = {}, {}, {"身体": "完好", "衣服": "完好"}
                st.session_state.npc_states = {} 
                st.session_state.last_deltas = {"hp": 0, "max_hp": 0, "mana": 0, "max_mana": 0}
                st.session_state.chat_messages, st.session_state.context_history, st.session_state.state_snapshots = [{"role": "ai", "content": final_opening, "type": "story"}], [final_opening], []
                st.session_state.session_id, st.session_state.session_save_name = datetime.now().strftime("%Y%m%d_%H%M%S"), save_name_input.strip()
                st.session_state.game_over, st.session_state.game_started = False, True
                utils.auto_save_game()
                st.rerun()

    with tab_saves: render_saves_tab(utils.SAVE_DIR)
    with tab_char: render_char_tab(char_dict)
    with tab_world: render_world_tab(world_dict, ai_engine)
    with tab_style: render_style_tab(style_dict, ai_engine, global_settings)
    
    # 【新增代码块】：渲染引擎控制台
    with tab_prompts:
        st.info("⚠️ 这里是引擎的底层法则核心（Prompt）。任何修改都会立刻全局生效，深刻影响世界演化逻辑。")
        prompt_path = os.path.join(utils.BASE_DIR, 'system_prompts.yml')
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f: current_prompts = yaml.safe_load(f)
        except Exception: current_prompts = {}
        
        with st.form("sys_prompt_form"):
            react_p = st.text_area("🧠 变数推演核心 (Reaction Prompt)", value=current_prompts.get('reaction_prompt', ''), height=200)
            settle_p = st.text_area("✍️ 剧情结算与演化核心 (Settlement Prompt)", value=current_prompts.get('settlement_prompt', ''), height=300)
            arch_p = st.text_area("🌍 世界架构师核心 (Architect Prompt)", value=current_prompts.get('world_architect_prompt', ''), height=150)
            
            if st.form_submit_button("💾 覆写底层法则", type="primary"):
                current_prompts['reaction_prompt'] = react_p
                current_prompts['settlement_prompt'] = settle_p
                current_prompts['world_architect_prompt'] = arch_p
                with open(prompt_path, 'w', encoding='utf-8') as f: yaml.dump(current_prompts, f, allow_unicode=True)
                st.success("法则修改成功！将在下一次推演中生效。")
                st.rerun()

def render_saves_tab(save_dir):
    saves = {}
    for f in glob.glob(os.path.join(save_dir, "*.json")):
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
            log.info(f"玩家载入存档: {sel_save_name}", extra={'module_name': '档案馆'})
            for k in ['char_info', 'style_info', 'world_info_base', 'world_entries', 'player_state', 'dynamic_bars', 'active_buffs', 'player_properties', 'npc_states', 'last_deltas', 'chat_messages', 'context_history', 'state_snapshots']:
                st.session_state[k] = sel_save.get(k, "" if k == 'world_info_base' else ([] if k in ['world_entries', 'state_snapshots'] else {}))
            st.session_state.session_id, st.session_state.session_save_name = datetime.now().strftime("%Y%m%d_%H%M%S"), sel_save_name
            st.session_state.game_over, st.session_state.game_started = False, True
            st.rerun()
        if c2.button("🗑️ 删除存档", type="secondary", use_container_width=True):
            os.remove(sel_save['_filepath'])
            st.rerun()

def render_char_tab(char_dict):
    mode = st.radio("模式", ["✨ 创建", "✏️ 编辑"], key="c_mode", horizontal=True)
    edit_target = char_dict[st.selectbox("选择", list(char_dict.keys()), key="c_sel")] if mode == "✏️ 编辑" and char_dict else None
    if mode == "✏️ 编辑" and edit_target:
        if st.button("🗑️ 删除该角色卡", type="secondary"): os.remove(edit_target['_filepath']); st.success("已删除！"); st.rerun()
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

def render_world_tab(world_dict, ai_engine):
    if 'ai_world_draft' not in st.session_state: st.session_state.ai_world_draft = None
    if 'ai_entry_draft' not in st.session_state: st.session_state.ai_entry_draft = ""
    with st.expander("🧠 AI 世界架构师", expanded=False):
        world_idea = st.text_input("输入灵感（例：赛博修仙...）")
        if st.button("✨ 创造世界"):
            with st.spinner("构筑中..."):
                draft = ai_engine.generate_worldbook(world_idea)
                if draft: st.session_state.ai_world_draft = draft; st.success("成功！请在下方确认并保存。")
    with st.expander("📝 AI 词条铸造机", expanded=False):
        entry_idea = st.text_area("输入设定灵感")
        if st.button("✨ 扩写词条"):
            with st.spinner("丰富细节中..."): st.session_state.ai_entry_draft = ai_engine.expand_world_entry(entry_idea)
        if st.session_state.ai_entry_draft: st.info(st.session_state.ai_entry_draft)

    wmode = st.radio("模式", ["✨ 创建新世界", "✏️ 编辑世界"], key="w_mode", horizontal=True)
    wedit_target = world_dict[st.selectbox("选择世界", list(world_dict.keys()), key="w_sel")] if wmode == "✏️ 编辑世界" and world_dict else None
    if wmode == "✏️ 编辑世界" and wedit_target:
        if st.button("🗑️ 删除该世界书", type="secondary"): os.remove(wedit_target['_filepath']); st.success("已删除！"); st.rerun()

    draft = st.session_state.ai_world_draft
    def_name = draft['name'] if draft else (wedit_target['name'] if wedit_target else "")
    def_global = draft['global_setting'] if draft else (wedit_target.get('global_setting', '') if wedit_target else "")
    def_open = draft['starting_scene'] if draft else (wedit_target.get('starting_scene', '') if wedit_target else "")
    def_entries = draft['entries'] if draft else (wedit_target.get('entries', [{"name": "范例", "keys": "关键字1", "content": "设定..."}]) if wedit_target else [{"name": "", "keys": "", "content": ""}])

    w_name = st.text_input("世界名称", value=def_name)
    w_global = st.text_area("常驻世界法则", value=def_global, height=100)
    w_open = st.text_area("世界开场白", value=def_open, height=100)
    
    df = pd.DataFrame(def_entries)
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True)
    
    if st.button("💾 保存世界书", type="primary") and w_name.strip():
        world_data = {"name": w_name.strip(), "global_setting": w_global, "starting_scene": w_open, "entries": edited_df.dropna(how="all").to_dict('records')}
        safe_fn = "".join(x for x in w_name if x.isalnum() or x in " _-")
        if wedit_target and wedit_target['name'] != w_name: os.remove(wedit_target['_filepath'])
        with open(os.path.join(utils.WORLD_DIR, f"{safe_fn}.yml"), 'w', encoding='utf-8') as f: yaml.dump(world_data, f, allow_unicode=True)
        st.session_state.ai_world_draft = None 
        st.rerun()

def render_style_tab(style_dict, ai_engine, global_settings):
    if 'ai_style_draft' not in st.session_state: st.session_state.ai_style_draft = ""
    with st.expander("🧙‍♂️ AI 文风大师", expanded=False):
        ai_hint = st.text_input("你想塑造什么样的文风？")
        if st.button("✨ 生成提示词"):
            with st.spinner("生成中..."): st.session_state.ai_style_draft = ai_engine.expand_style(ai_hint)
            
    smode = st.radio("模式", ["✨ 创建文风", "✏️ 编辑文风"], key="s_mode", horizontal=True)
    sedit_target = style_dict[st.selectbox("选择文风", list(style_dict.keys()), key="s_sel")] if smode == "✏️ 编辑文风" and style_dict else None
    if smode == "✏️ 编辑文风" and sedit_target:
        if st.button("🗑️ 删除该文风", type="secondary"): os.remove(sedit_target['_filepath']); st.success("已删除！"); st.rerun()

    with st.form("style_form"):
        s_name = st.text_input("文风名称", value=sedit_target['name'] if sedit_target else "")
        default_content = st.session_state.ai_style_draft if st.session_state.ai_style_draft else (sedit_target['content'] if sedit_target else "")
        s_content = st.text_area("提示词要求", value=default_content, height=150)
        c1, c2 = st.columns(2)
        if c1.form_submit_button("💾 保存", type="primary") and s_name.strip():
            safe_fn = "".join(x for x in s_name if x.isalnum() or x in " _-")
            if sedit_target and sedit_target['name'] != s_name: os.remove(sedit_target['_filepath'])
            with open(os.path.join(utils.STYLE_DIR, f"{safe_fn}.yml"), 'w', encoding='utf-8') as f: yaml.dump({"name": s_name.strip(), "content": s_content}, f, allow_unicode=True)
            st.session_state.ai_style_draft = ""
            st.rerun()
        if c2.form_submit_button("⭐ 设为默认") and s_name.strip():
            global_settings['default_style'] = s_name.strip(); utils.save_settings(global_settings); st.success("已设为默认！")