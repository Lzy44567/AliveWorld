# core/context_manager.py
import os, glob, yaml
from core.worldbook import WorldbookRetriever, normalize_worldbook
from core.worldbook_embeddings import embedding_manager
from utils.sys_logger import get_logger

log = get_logger()

class ContextManager:
    def __init__(self, worldbook_retriever=None):
        self.char_info = ""
        self.style_info = ""
        self.world_info_base = ""
        self.world_entries = []
        self.worldbook_retriever = worldbook_retriever or WorldbookRetriever(semantic=embedding_manager)

    def refresh_from_local(self, save_dir_path, description):
        if not save_dir_path or not os.path.exists(save_dir_path): return

        styles = []
        for f in glob.glob(os.path.join(save_dir_path, 'styles', '*.yml')):
            with open(f, 'r', encoding='utf-8') as file:
                data = normalize_worldbook(yaml.safe_load(file))
                if data and data.get('is_active', True): styles.append(data.get('content', ''))
        self.style_info = "\n---\n".join(styles)

        worlds_base = []
        self.world_entries = []
        for f in glob.glob(os.path.join(save_dir_path, 'worldbooks', '*.yml')):
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and data.get('is_active', True):
                    if data.get('global_setting'): worlds_base.append(f"[{data.get('name', '界域法则')}]：{data.get('global_setting')}")
                    self.world_entries.extend(data.get('entries', []))
        self.world_info_base = "\n".join(worlds_base)

        player_chars, npc_chars = [], []
        for f in glob.glob(os.path.join(save_dir_path, 'characters', '*.yml')):
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and data.get('is_active', True):
                    desc = f"[{data.get('name', '未知实体')}]：{data.get('description', '')}"
                    if data.get('is_player', False): player_chars.append(desc)
                    else: npc_chars.append(desc)
        
        self.char_info = "\n---\n".join(player_chars) if player_chars else "无名冒险者"
        if npc_chars: self.world_info_base += "\n\n【当前登场的重要NPC与势力】：\n" + "\n".join(npc_chars)
        if description: self.world_info_base = f"【🔥宇宙主导向 (最高法则)】：{description}\n\n" + self.world_info_base


    def build_active_world_info(self, context_text, action, shadow_ledger):
        active = self.world_info_base + "\n"
        search = context_text + "\n" + action
        hits, omitted = self.worldbook_retriever.retrieve(self.world_entries, search)
        triggered = []
        for hit in hits:
            ent = hit.entry
            active += f"【设定 - {ent.get('name')}】：{ent.get('content', '')}\n"
            triggered.append(ent.get('name'))
            log.info("世界书条目命中: id=%s name=%s reasons=%s score=%.3f", ent["id"], ent["name"], list(hit.reasons), hit.score)
        for hit in omitted:
            log.info("世界书条目因上下文预算省略: id=%s name=%s score=%.3f", hit.entry["id"], hit.entry["name"], hit.score)
        active += "\n【隐藏的暗流因果】：\n" + shadow_ledger
        return active, triggered
