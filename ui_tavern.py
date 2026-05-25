# ui_tavern.py
import streamlit as st
import os, yaml, json
import pandas as pd
from datetime import datetime
import utils

def render_saves_tab(saves):
    if not saves: st.info("当前没有任何存档。")
    else:
        sel_save_name = st.selectbox("📂 选择存档", list(saves.keys()))
        sel_save = saves[sel_save_name]
        c1, c2 = st.columns(2)
        if c1.button("📂 载入故事线", type="primary", use_container_width=True):
            st.session_state.log_file = utils.setup_logger()
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