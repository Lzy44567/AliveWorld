# core/undercurrent.py
from utils.sys_logger import get_logger
from core.prompts import load_system_prompts

log = get_logger()

class Entity:
    def __init__(self, name, goal, max_cooldown):
        self.name = name
        self.goal = goal
        self.max_cooldown = max_cooldown
        self.current_cooldown = max_cooldown  # 当前剩余冷却

    def to_dict(self):
        return {"name": self.name, "goal": self.goal, "max_cooldown": self.max_cooldown, "current_cooldown": self.current_cooldown}

    @classmethod
    def from_dict(cls, data):
        ent = cls(data['name'], data['goal'], data['max_cooldown'])
        ent.current_cooldown = data.get('current_cooldown', data['max_cooldown'])
        return ent


class UndercurrentEngine:
    def __init__(self, ai_engine):
        self.ai_engine = ai_engine
        self.tick_count = 0
        self.shadow_ledger = [] # 因果账本
        self.entities = []      # 潜伏的实体列表

        # MVP 默认插入一个“世界意志”实体
        self.entities.append(Entity(name="世界意志 (命运暗流)", goal="在不为人知的角落推进世界的混乱，引发意外事件", max_cooldown=3))

    def load_state(self, data):
        self.tick_count = data.get('tick_count', 0)
        self.shadow_ledger = data.get('shadow_ledger', [])
        if 'entities' in data:
            self.entities = [Entity.from_dict(e) for e in data['entities']]

    def export_state(self):
        return {
            "tick_count": self.tick_count, 
            "shadow_ledger": self.shadow_ledger,
            "entities": [e.to_dict() for e in self.entities]
        }

    def tick(self, world_context_text):
        """主线推进时，暗流系统运转"""
        self.tick_count += 1
        log.info(f"暗流时间流转: Tick {self.tick_count}")
        
        events_this_turn = []
        
        for entity in self.entities:
            entity.current_cooldown -= 1
            if entity.current_cooldown <= 0:
                log.info(f"实体觉醒推演: {entity.name}")
                # 触发独立 AI 推演实体的行动
                event_desc = self._infer_entity_action(entity, world_context_text)
                
                if event_desc:
                    events_this_turn.append(f"【{entity.name}】：{event_desc}")
                    # 写入永久账本
                    self.shadow_ledger.append(f"[Tick {self.tick_count}] {entity.name}暗中行动：{event_desc}")
                
                # 重置冷却
                entity.current_cooldown = entity.max_cooldown
                
        return events_this_turn

    def _infer_entity_action(self, entity, context):
        pts = load_system_prompts()
        prompt_sys = pts.get('entity_action_prompt', '你是一个推演神明。推断该实体的下一步举动（一句客观描述）。')
        
        prompt_sys = prompt_sys.replace("{world_context}", context)
        prompt_sys = prompt_sys.replace("{entity_name}", entity.name)
        prompt_sys = prompt_sys.replace("{entity_goal}", entity.goal)
        
        # 实体推演不需要复杂的 JSON，我们直接用常规文本获取，节约开销和时间
        raw_ans, err = self.ai_engine.chat_json(prompt_sys, "请输出实体的行动，不要带任何JSON格式。", temp=0.9)
        
        # 兼容一下，因为 chat_json 默认是 json object 返回，这里如果大模型强行包了 json，我们就剥离它
        if "{" in raw_ans and "}" in raw_ans:
            import json, re
            try:
                # 尝试用正则挖取值
                match = re.search(r'\"(.*?)\"', raw_ans)
                if match: return match.group(1)
            except: pass
        
        return raw_ans.strip() if not err else ""

    def get_ledger_context(self):
        """将最近的暗流提取给主线大模型做背景蝴蝶效应"""
        if not self.shadow_ledger: return "（世界目前风平浪静）"
        # 只取最近 3 条，防止影响主线权重过大
        return "\n".join(self.shadow_ledger[-3:])