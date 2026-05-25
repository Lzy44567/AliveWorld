# ui_tavern.py
import streamlit as st
import os, yaml, pandas as pd
from utils import file_io
from core.game_session import GameSession

def render_tavern(ai_engine, global_settings):
    st.title("🏰 AliveWorld - 多元宇宙大厅")
    t_lobby, t_saves, t_char, t_world, t_style = st.tabs(["🚀 开启新故事", "📂 记忆档案馆", "🗂️ 角色工坊", "🌍 世界书工坊", "🎭 文风工坊"])
    
    char_dict = file_io.load_yaml_files(file_io.CHAR_DIR)
    style_dict = file_io.load_yaml_files(file_io.STYLE_DIR)
    world_dict = file_io.load_yaml_files(file_io.WORLD_DIR)
    
    with t_lobby:
        if not char_dict: st.warning("请先去【角色工坊】创建一张角色卡。")
        else:
            save_name_input = st.text_input("📝 为本次冒险命名 (必填)", value="")
            c1, c2, c3 = st.columns(3)
            sel_c = c1.selectbox("📝 选择化身", list(char_dict.keys()))
            style_options = ["默认 (无)"] + list(style_dict.keys())
            def_style_idx = style_options.index(global_settings.get('default_style', '默认 (无)')) if global_settings.get('default_style') in style_options else 0
            sel_s = c2.selectbox("🎭 选择文风", style_options, index=def_style_idx)
            sel_w = c3.selectbox("🌍 载入世界书", ["无界域 (暂不加载)"] + list(world_dict.keys()))
            
            sel_char = char_dict[sel_c]
            final_opening = (world_dict[sel_w].get('starting_scene', '') + "\n\n" + sel_char.get('starting_scene', '')) if sel_w != "无界域 (暂不加载)" else sel_char.get('starting_scene', '')
            with st.container(border=True):
                st.markdown(f"**📖 角色设定:** {sel_char.get('description', '无')}")
                st.markdown(f"**🎬 最终开场白:** {final_opening[:100]}...")

            if st.button("🚀 链接新世界", type="primary", use_container_width=True, disabled=not save_name_input.strip()):
                game = GameSession(ai_engine, save_name_input.strip())
                s_cont = style_dict[sel_s]['content'] if sel_s != "默认 (无)" else ""
                w_cont = world_dict[sel_w] if sel_w != "无界域 (暂不加载)" else {}
                game.start_new_game(sel_char, s_cont, w_cont, final_opening)
                st.session_state.game = game
                file_io.save_game_data(game.save_name, game.export_save_data())
                st.rerun()

    with t_saves:
        saves = file_io.get_all_saves()
        if not saves: st.info("当前没有任何存档。")
        else:
            sel_save_name = st.selectbox("📂 选择存档", list(saves.keys()))
            sel_save = saves[sel_save_name]
            c1, c2 = st.columns(2)
            if c1.button("📂 载入故事线", type="primary", use_container_width=True):
                game = GameSession(ai_engine)
                game.load_save_data(sel_save)
                st.session_state.game = game
                st.rerun()
            if c2.button("🗑️ 删除存档", type="secondary", use_container_width=True):
                os.remove(sel_save['_filepath'])
                st.rerun()

    with t_char:
        mode = st.radio("模式", ["✨ 创建", "✏️ 编辑"], key="c_mode", horizontal=True)
        edit_target = char_dict[st.selectbox("选择", list(char_dict.keys()), key="c_sel")] if mode == "✏️ 编辑" and char_dict else None
        if mode == "✏️ 编辑" and edit_target:
            if st.button("🗑️ 删除该角色卡", type="secondary"): os.remove(edit_target['_filepath']); st.rerun()
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
                with open(os.path.join(file_io.CHAR_DIR, f"{safe_fn}.yml"), 'w', encoding='utf-8') as f:
                    yaml.dump({"name": f_name.strip(), "type": f_type, "initial_hp": f_hp, "initial_mana": f_mana, "description": f_desc, "starting_scene": f_scene}, f, allow_unicode=True)
                st.rerun()

    with t_world:
        wmode = st.radio("模式", ["✨ 创建新世界", "✏️ 编辑世界"], key="w_mode", horizontal=True)
        wedit_target = world_dict[st.selectbox("选择世界", list(world_dict.keys()), key="w_sel")] if wmode == "✏️ 编辑世界" and world_dict else None
        if wmode == "✏️ 编辑世界" and wedit_target:
            if st.button("🗑️ 删除该世界书", type="secondary"): os.remove(wedit_target['_filepath']); st.rerun()
        w_name = st.text_input("世界名称", value=wedit_target['name'] if wedit_target else "")
        w_global = st.text_area("常驻世界法则", value=wedit_target.get('global_setting', '') if wedit_target else "", height=100)
        w_open = st.text_area("世界开场白", value=wedit_target.get('starting_scene', '') if wedit_target else "", height=100)
        df = pd.DataFrame(wedit_target.get('entries', [{"name": "", "keys": "", "content": ""}]) if wedit_target else [{"name": "", "keys": "", "content": ""}])
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True)
        if st.button("💾 保存世界书", type="primary") and w_name.strip():
            world_data = {"name": w_name.strip(), "global_setting": w_global, "starting_scene": w_open, "entries": edited_df.dropna(how="all").to_dict('records')}
            safe_fn = "".join(x for x in w_name if x.isalnum() or x in " _-")
            if wedit_target and wedit_target['name'] != w_name: os.remove(wedit_target['_filepath'])
            with open(os.path.join(file_io.WORLD_DIR, f"{safe_fn}.yml"), 'w', encoding='utf-8') as f: yaml.dump(world_data, f, allow_unicode=True)
            st.rerun()

    with t_style:
        smode = st.radio("模式", ["✨ 创建文风", "✏️ 编辑文风"], key="s_mode", horizontal=True)
        sedit_target = style_dict[st.selectbox("选择文风", list(style_dict.keys()), key="s_sel")] if smode == "✏️ 编辑文风" and style_dict else None
        if smode == "✏️ 编辑文风" and sedit_target:
            if st.button("🗑️ 删除该文风", type="secondary"): os.remove(sedit_target['_filepath']); st.rerun()
        with st.form("style_form"):
            s_name = st.text_input("文风名称", value=sedit_target['name'] if sedit_target else "")
            s_content = st.text_area("提示词要求", value=sedit_target['content'] if sedit_target else "", height=150)
            c1, c2 = st.columns(2)
            if c1.form_submit_button("💾 保存", type="primary") and s_name.strip():
                safe_fn = "".join(x for x in s_name if x.isalnum() or x in " _-")
                if sedit_target and sedit_target['name'] != s_name: os.remove(sedit_target['_filepath'])
                with open(os.path.join(file_io.STYLE_DIR, f"{safe_fn}.yml"), 'w', encoding='utf-8') as f: yaml.dump({"name": s_name.strip(), "content": s_content}, f, allow_unicode=True)
                st.rerun()
            if c2.form_submit_button("⭐ 设为默认") and s_name.strip():
                global_settings['default_style'] = s_name.strip(); file_io.save_settings(global_settings); st.success("已设为默认！")