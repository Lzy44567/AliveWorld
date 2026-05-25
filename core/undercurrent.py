# core/undercurrent.py
from utils.sys_logger import get_logger
log = get_logger()

class UndercurrentEngine:
    def __init__(self):
        self.tick_count = 0
        self.shadow_ledger = [] # 记录因果账本
        self.entities = {} # 未来的势力和NPC实体存在这里

    def load_state(self, data):
        self.tick_count = data.get('tick_count', 0)
        self.shadow_ledger = data.get('shadow_ledger', [])

    def export_state(self):
        return {"tick_count": self.tick_count, "shadow_ledger": self.shadow_ledger}

    def tick(self, world_events_from_main_ai=None):
        """推进世界时间"""
        self.tick_count += 1
        # 记录主线AI结算时产生的暗流
        if world_events_from_main_ai:
            for ev in world_events_from_main_ai:
                self.shadow_ledger.append(f"[Tick {self.tick_count}] {ev}")
        
        # 预留给未来：如果 tick 到了特定时间，触发其他实体独立的 AI API 推演
        # for entity in self.entities: if entity.cooldown == 0: entity.act()

    def get_ledger_context(self):
        """将最近的暗流提取给主推演引擎做背景"""
        if not self.shadow_ledger: return ""
        recent = self.shadow_ledger[-5:] # 只取最近5条防止Prompt过长
        return "\n".join(recent)