# core/undercurrent.py
# 100% 完整底稿 (请直接覆盖原文件)

from utils.sys_logger import get_logger
from core.prompts import load_system_prompts
from core.ai_engine import robust_json_parse
from core.entities import Entity, active_entities
from core.shadow_ledger import ShadowLedger
from core.causal_ledger import CausalLedger

log = get_logger()

class UndercurrentEngine:
    def __init__(self, ai_engine):
        self.ai_engine = ai_engine
        self.tick_count = 0
        self.ledger = ShadowLedger()
        self.causal_ledger = CausalLedger()
        # 🚀 修复问题 1：彻底清空硬编码幽灵实体！现在完全由本地文件决定！
        self.entities = []

    def load_state(self, data):
        self.tick_count = data.get('tick_count', 0)
        self.ledger = ShadowLedger(data.get('shadow_ledger', []))
        self.causal_ledger = CausalLedger(data.get('causal_ledger', []), turn_count=data.get('causal_turn_count', 0))
        if 'entities' in data: self.entities = [Entity.from_dict(e) for e in data['entities']]

    def export_state(self):
        return {"tick_count": self.tick_count, "shadow_ledger": self.ledger.export(), "causal_ledger": self.causal_ledger.export(), "causal_turn_count": self.causal_ledger.turn_count, "entities": [e.to_dict() for e in self.entities]}

    def sync_influence_refs(self):
        for entity in self.entities:
            entity.influence_refs = self.causal_ledger.refs_for_entity(entity.name)

    def has_active_entities(self):
        return any(active_entities(self.entities))

    def tick(self, world_context_text, enabled=True, world_time=""):
        if not enabled:
            log.info("跳过 Overseer：玩家已关闭暗流实体推演总开关。")
            return []
        if not self.has_active_entities():
            log.info("跳过 Overseer：局内没有启用中的暗流实体。")
            return []

        self.tick_count += 1
        log.info(f"=== 暗流时间流转: Tick {self.tick_count} ===")
        
        pts = load_system_prompts()
        prompt_sys = pts.get('overseer_prompt', '')
        if not prompt_sys:
            log.error("未找到 overseer_prompt 法则，暗流中止。")
            return []
        
        active_by_name = {entity.name: entity for entity in active_entities(self.entities)}
        ent_info = "\n".join(entity.prompt_summary() for entity in active_by_name.values())
        prompt_sys = prompt_sys.replace("{entities_info}", ent_info)
        prompt_sys = prompt_sys.replace("{world_context}", world_context_text)
        
        raw_ans, err = self.ai_engine.chat_json(prompt_sys, "请推演实体的幕后行动与生灭。无动作的数组必须留空 []。", temp=0.8, trace_label="Overseer实体推演")
        
        events_this_turn = []
        if err or not raw_ans:
            log.warning(f"Overseer 响应异常: {err}")
            return events_this_turn
            
        try:
            res = robust_json_parse(raw_ans)
            
            events = res.get("undercurrent_events", [])
            for ev in events:
                ent_name = ev.get("entity", "未知实体")
                act = ev.get("action", "")
                entity = active_by_name.get(ent_name)
                if act and entity:
                    details = {
                        field: ev[field]
                        for field in ("status", "new_plans", "new_mechanisms", "new_triggers", "relationship_updates")
                        if field in ev
                    }
                    events_this_turn.append(f"【{ent_name}】：{act}")
                    self.ledger.record(self.tick_count, "action", ent_name, act, ev.get("clues", []), details)
                    entity.apply_action(ev)
                    log.info(f"暗流发生: 【{ent_name}】 {act}")
                elif act:
                    log.warning(f"忽略非活跃或不存在实体的行动: {ent_name}")
            
            new_ents = res.get("new_entities", [])
            for ne in new_ents:
                n_name = ne.get("name", "")
                n_goal = ne.get("motive", ne.get("goal", ""))
                if n_name and not any(e.name == n_name for e in self.entities):
                    new_entity = Entity.from_dict(ne)
                    self.entities.append(new_entity)
                    events_this_turn.append(f"🌟 变数潜入暗流：[{n_name}]")
                    self.ledger.record(self.tick_count, "entity_created", n_name, f"实体诞生：{n_goal}")
                    log.info(f"新实体诞生: {n_name} - {n_goal}")

            for influence_data in res.get("new_influences", []):
                if isinstance(influence_data, dict) and not influence_data.get("created_world_time"):
                    influence_data = {**influence_data, "created_world_time": world_time}
                influence = self.causal_ledger.add(influence_data, current_tick=self.causal_ledger.turn_count)
                valid_sources = {entity.name for entity in active_entities(self.entities)}
                source_names = {link.get("entity") for link in influence.source_links} if influence else set()
                if influence and source_names and source_names.issubset(valid_sources):
                    log.info(f"暗流影响创建: [{influence.id}] {influence.summary}")
                elif influence:
                    self.causal_ledger.remove(influence.id)
                    log.warning(f"忽略来源实体无效的暗流影响: [{influence.id}] {source_names}")

            for influence_data in res.get("update_influences", []):
                requested_links = influence_data.get("source_links") if isinstance(influence_data, dict) else None
                valid_sources = {entity.name for entity in active_entities(self.entities)}
                requested_sources = {
                    link.get("entity") if isinstance(link, dict) else str(link)
                    for link in (requested_links or [])
                }
                if requested_links is not None and (not requested_sources or not requested_sources.issubset(valid_sources)):
                    log.warning(f"忽略来源实体无效的暗流影响更新: {requested_sources}")
                    continue
                influence = self.causal_ledger.update(influence_data)
                if influence:
                    log.info(f"暗流影响更新: [{influence.id}] {influence.summary}")

            for influence_id in res.get("delete_influences", []):
                influence = self.causal_ledger.remove(str(influence_id))
                if influence:
                    log.info(f"暗流影响取消: [{influence.id}] {influence.summary}")
                    
            up_ents = res.get("update_entities", [])
            for ue in up_ents:
                u_name = ue.get("name", "")
                u_goal = ue.get("motive", ue.get("goal", ""))
                entity = active_by_name.get(u_name)
                if entity:
                    if u_goal:
                        log.info(f"实体动机转变: {entity.name} -> {u_goal}")
                    entity.apply_update(ue)
                elif u_name:
                    log.warning(f"忽略非活跃或不存在实体的更新: {u_name}")
            
            del_ents = res.get("delete_entities", [])
            for de_name in del_ents:
                if de_name not in active_by_name:
                    log.warning(f"忽略非活跃或不存在实体的删除: {de_name}")
                    continue
                death_result = self.causal_ledger.handle_source_death(de_name)
                for influence in death_result["released"]:
                    log.info(f"实体死亡释放影响: [{influence.id}] {influence.summary}")
                for influence in death_result["removed"]:
                    log.info(f"实体死亡移除影响: [{influence.id}] {influence.summary}")
                original_len = len(self.entities)
                self.entities = [e for e in self.entities if e.name != de_name]
                if len(self.entities) < original_len:
                    log.info(f"实体湮灭: {de_name}")
                    events_this_turn.append(f"💀 某股势力消亡了：[{de_name}]")
                    self.ledger.record(self.tick_count, "entity_deleted", de_name, "实体湮灭")

            self.sync_influence_refs()
                        
        except Exception as e:
            log.error(f"Overseer JSON 解析失败: {e}\nRaw: {raw_ans}")
            
        return events_this_turn

    def get_ledger_context(self):
        return self.ledger.context() + "\n\n【暗流因果账本】\n" + self.causal_ledger.context()
