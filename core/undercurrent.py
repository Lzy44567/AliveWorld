# core/undercurrent.py
from utils.sys_logger import get_logger
from core.prompts import load_system_prompts

log = get_logger()

# ...(Entity 类的定义保持不变，此处省略展示以节约空间) ...
class Entity:
    def __init__(self, name, goal, max_cooldown):
        self.name = name; self.goal = goal; self.max_cooldown = max_cooldown; self.current_cooldown = max_cooldown
    def to_dict(self): return {"name": self.name, "goal": self.goal, "max_cooldown": self.max_cooldown, "current_cooldown": self.current_cooldown}
    @classmethod
    def from_dict(cls, data):
        ent = cls(data['name'], data['goal'], data['max_cooldown'])
        ent.current_cooldown = data.get('current_cooldown', data['max_cooldown'])
        return ent

class UndercurrentEngine:
    def __init__(self, ai_engine):
        self.ai_engine = ai_engine
        self.tick_count = 0
        self.shadow_ledger = [] 
        self.entities = [Entity(name="世界意志 (命运暗流)", goal="在不为人知的角落推进世界的混乱，引发意外事件", max_cooldown=3)]

    def load_state(self, data):
        self.tick_count = data.get('tick_count', 0)
        self.shadow_ledger = data.get('shadow_ledger', [])
        if 'entities' in data: self.entities = [Entity.from_dict(e) for e in data['entities']]

    def export_state(self): return {"tick_count": self.tick_count, "shadow_ledger": self.shadow_ledger, "entities": [e.to_dict() for e in self.entities]}

    def tick(self, world_context_text):
        self.tick_count += 1
        log.info(f"暗流时间流转: Tick {self.tick_count}")
        events_this_turn = []
        
        for entity in self.entities:
            entity.current_cooldown -= 1
            if entity.current_cooldown <= 0:
                log.info(f"实体觉醒推演: {entity.name}")
                event_desc = self._infer_entity_action(entity, world_context_text)
                
                if event_desc:
                    events_this_turn.append(f"【{entity.name}】：{event_desc}")
                    self.shadow_ledger.append(f"[Tick {self.tick_count}] {entity.name}暗中行动：{event_desc}")
                    # 【修复】把暗流推演结果打印到系统日志！
                    log.info(f"暗流成功生成: {event_desc}") 
                
                entity.current_cooldown = entity.max_cooldown
        return events_this_turn

    def _infer_entity_action(self, entity, context):
        pts = load_system_prompts()
        prompt_sys = pts.get('entity_action_prompt', '你是一个推演神明。推断该实体的下一步举动（一句客观描述）。')
        prompt_sys = prompt_sys.replace("{world_context}", context).replace("{entity_name}", entity.name).replace("{entity_goal}", entity.goal)
        
        # 【修复】使用 chat_text 代替 chat_json！不再报错！
        raw_ans, err = self.ai_engine.chat_text(prompt_sys, "请输出实体的行动，不要带任何JSON格式或废话。", temp=0.9)
        return raw_ans.strip() if not err else ""

    def get_ledger_context(self):
        if not self.shadow_ledger: return "（世界目前风平浪静）"
        return "\n".join(self.shadow_ledger[-3:])