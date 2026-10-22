# core/context_manager.py
import os, glob, yaml
from core.worldbook import WorldbookRetriever, build_retrieval_query, normalize_worldbook
from core.worldbook_embeddings import embedding_manager
from core.worldbook_revisions import reconcile_capture_history
from core.worldbook_collaboration import load_books, primary_book, rule_catalog, disabled_references
from utils.sys_logger import get_logger

log = get_logger()

class ContextManager:
    def __init__(self, worldbook_retriever=None):
        self.char_info = ""
        self.style_info = ""
        self.world_info_base = ""
        self.world_entries = []
        self.world_rules = {}
        self.supplied_world_rules = {}
        self.world_books = {}
        self.primary_worldbook = ""
        self.worldbook_retriever = worldbook_retriever or WorldbookRetriever(semantic=embedding_manager)

    def refresh_from_local(self, save_dir_path, description, *, active_turns=None, collaboration=None):
        if not save_dir_path or not os.path.exists(save_dir_path): return

        styles = []
        for f in glob.glob(os.path.join(save_dir_path, 'styles', '*.yml')):
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if data and data.get('is_active', True): styles.append(data.get('content', ''))
        self.style_info = "\n---\n".join(styles)

        worlds_base = []
        self.world_entries = []
        for f in ([] if collaboration is not None else glob.glob(os.path.join(save_dir_path, 'worldbooks', '*.yml'))):
            with open(f, 'r', encoding='utf-8') as file:
                data = normalize_worldbook(yaml.safe_load(file))
                if active_turns is not None and data.get('capture_history'):
                    data, _ = reconcile_capture_history(data, active_turns)
                if data and data.get('is_active', True):
                    if data.get('overview'): worlds_base.append(f"【{data.get('name', '世界')} · 概述】：{data.get('overview')}")
                    if data.get('axioms'): worlds_base.append("【世界公理】：\n" + "\n".join(f"- {item}" for item in data.get('axioms', [])))
                    self.world_entries.extend(data.get('entries', []))
        self.world_info_base = "\n".join(worlds_base)
        self.world_rules = {}
        self.supplied_world_rules = {}
        if collaboration is not None:
            self._prepare_collaborative_worlds(save_dir_path, active_turns or [], collaboration)

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
        if description: self.world_info_base = f"【故事与世界概述】：{description}\n\n" + self.world_info_base

    def _prepare_collaborative_worlds(self, save_dir, turns, collaboration):
        self.world_books = load_books(save_dir, turns)
        self.primary_worldbook = primary_book(collaboration, self.world_books)
        self.world_rules = rule_catalog(self.world_books)
        disabled = disabled_references(collaboration, self.world_books, turns)
        self.world_entries = []
        base = []
        for ref, rule in self.world_rules.items():
            if ref in disabled:
                continue
            role = ("主世界书" if rule["book_id"] == self.primary_worldbook else "补充知识书") if self.primary_worldbook else "未指定主次"
            if rule["kind"] == "entry":
                entry = next(item for item in self.world_books[rule["book_id"]]["entries"] if item["id"] == rule["item_id"])
                self.world_entries.append({**entry, "id": ref})
            else:
                base.append(f"【{role} · {rule['book_name']} · {rule['name']} · 引用 {ref}】：{rule['content']}")
        self.world_info_base = "\n".join(base)


    def build_visible_world_info(self, context_text, action):
        active = self.world_info_base + "\n"
        search = build_retrieval_query(context_text, action)
        hits, omitted = self.worldbook_retriever.retrieve(self.world_entries, search)
        self.supplied_world_rules = {ref: rule for ref, rule in self.world_rules.items() if rule['kind'] != 'entry'}
        triggered = []
        for hit in hits:
            ent = hit.entry
            rule = self.world_rules.get(ent['id'])
            if rule:
                role = ("主世界书" if rule['book_id'] == self.primary_worldbook else "补充知识书") if self.primary_worldbook else "未指定主次"
                active += f"【{role} · {rule['book_name']} · {ent.get('name')} · 引用 {ent['id']}】：{ent.get('content', '')}\n"
                self.supplied_world_rules[ent['id']] = rule
            else:
                active += f"【设定 - {ent.get('name')}】：{ent.get('content', '')}\n"
            triggered.append(ent.get('name'))
            log.info("世界书条目命中: id=%s name=%s reasons=%s score=%.3f", ent["id"], ent["name"], list(hit.reasons), hit.score)
        for hit in omitted:
            log.info("世界书条目因上下文预算省略: id=%s name=%s score=%.3f", hit.entry["id"], hit.entry["name"], hit.score)
        return active, triggered

    def build_active_world_info(self, context_text, action, shadow_ledger):
        active, triggered = self.build_visible_world_info(context_text, action)
        active += "\n【隐藏的暗流因果】：\n" + shadow_ledger
        return active, triggered
