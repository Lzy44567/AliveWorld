# core/state_manager.py
import copy
from dataclasses import dataclass
from typing import Any

from core.npc_presence import NpcPresenceTracker
from core.timed_effects import advance_effects, tick_effects


@dataclass(frozen=True)
class StateUpdatePlan:
    state: dict[str, Any]
    metadata: dict[str, Any]

class StateManager:
    def __init__(self):
        self.state = {
            "properties": {"身体": "完好"},
            "bars": {}, 
            "buffs": {}, 
            "npcs": {}
        }
        self.npc_presence = NpcPresenceTracker()

    def _apply_updates_in_place(self, result, *, story_text="", player_action="", tick=True):
        # 1. 增添新 Buffs
        for bn, bd in result.get('new_buffs', {}).items():
            if isinstance(bd, dict): 
                self.state['buffs'][bn] = bd

        # 2. 移除指定 Buffs
        remove_list = result.get('remove_buffs', [])
        if not isinstance(remove_list, list): 
            remove_list = []
        for bn in remove_list: 
            self.state['buffs'].pop(bn, None)
            
        # 3. 重置上一回合的变动显示
        if tick:
            for b in self.state['bars'].values():
                b['change'] = 0
            
        # 4. 🚀 修复Buff结算：智能匹配动态进度条的持续影响 (例如 生命值_per_turn: -5)
        if tick:
            tick_effects(self.state)

        # 5. 结算当回合 AI 给出的进度条变化
        for bn, bd in result.get('dynamic_bars', {}).items():
            if not isinstance(bd, dict): continue
            
            if bn not in self.state['bars']: 
                cur = bd.get('current', 0)
                self.state['bars'][bn] = {"current": cur, "max": bd.get('max', 100), "change": cur, "color": bd.get('color', 'indigo')}
            else:
                old_cur = self.state['bars'][bn]["current"]
                if 'current' in bd: self.state['bars'][bn]["current"] = bd['current']
                if 'max' in bd: self.state['bars'][bn]["max"] = bd['max']
                if 'color' in bd: self.state['bars'][bn]["color"] = bd['color']
                if 'change' in bd: self.state['bars'][bn]["current"] += bd['change']
                
                # 累加当回合的直接结算变动
                self.state['bars'][bn]["change"] += (self.state['bars'][bn]["current"] - old_cur)
                
        # 统一定界进度条，防止溢出或小于0
        for bn, bar in self.state['bars'].items():
            bar['current'] = max(0, min(bar['current'], bar.get("max", 100)))
                
        # 6. 结算当前场景 NPC；历史人物资料仍保留在角色卡与正文中。
        self.state['npcs'] = self.npc_presence.reconcile(
            self.state.get('npcs', {}), result.get('npc_states', {}),
            story_text=story_text, player_action=player_action,
        )
            
        # 7. 结算一般文本属性与时间
        for k, v in result.get('status_updates', {}).items(): 
            if isinstance(v, dict): v = ", ".join([f"{dk}:{dv}" for dk, dv in v.items()])
            self.state['properties'][k] = str(v)
            
        # 8. 彻底粉碎删除
        dels = result.get('status_deletions', [])
        if not isinstance(dels, list): dels = []
        for k in dels:
            for group in ['properties', 'bars', 'buffs', 'npcs']: 
                self.state[group].pop(k, None)
            self.npc_presence.absent_turns.pop(k, None)

    def plan_updates(self, result, *, story_text="", player_action="", effect_plan=None):
        """Calculate one turn on an isolated copy without mutating live state."""
        staged = StateManager()
        staged.state = copy.deepcopy(self.state if effect_plan is None else effect_plan.state)
        staged.load_metadata(copy.deepcopy(self.export_metadata() if effect_plan is None else effect_plan.metadata))
        staged._apply_updates_in_place(
            result, story_text=story_text, player_action=player_action,
            tick=effect_plan is None,
        )
        return StateUpdatePlan(
            state=copy.deepcopy(staged.state),
            metadata=copy.deepcopy(staged.export_metadata()),
        )

    def plan_effects(self, rounds, *, stop_at_zero=()):
        """Preview existing effects; new effects start after this time span."""
        state = copy.deepcopy(self.state)
        progress = advance_effects(state, rounds, stop_at_zero=stop_at_zero)
        return StateUpdatePlan(state, copy.deepcopy(self.export_metadata())), progress

    def commit(self, plan: StateUpdatePlan):
        if not isinstance(plan, StateUpdatePlan):
            raise TypeError("state update plan is required")
        self.state = copy.deepcopy(plan.state)
        self.load_metadata(copy.deepcopy(plan.metadata))

    def apply_updates(self, result, *, story_text="", player_action=""):
        plan = self.plan_updates(result, story_text=story_text, player_action=player_action)
        self.commit(plan)

    def get_dynamic_state(self):
        return { 
            "bars": self.state['bars'], "properties": self.state['properties'], 
            "buffs": self.state['buffs'], "npcs": self.state['npcs'] 
        }

    def export_metadata(self):
        return {"npc_presence": self.npc_presence.export_state()}

    def load_metadata(self, value):
        value = value if isinstance(value, dict) else {}
        self.npc_presence.load_state(value.get("npc_presence"))
