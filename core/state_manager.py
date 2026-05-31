# core/state_manager.py
import copy

class StateManager:
    def __init__(self):
        self.state = {
            "properties": {"身体": "完好"},
            "bars": {}, 
            "buffs": {}, 
            "npcs": {}
        }

    def apply_updates(self, result):
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
        for b in self.state['bars'].values(): 
            b['change'] = 0
            
        # 4. 🚀 修复Buff结算：智能匹配动态进度条的持续影响 (例如 生命值_per_turn: -5)
        to_remove = []
        for bn, bd in self.state['buffs'].items():
            for key, val in bd.items():
                if key.endswith('_per_turn'):
                    target_bar = key.replace('_per_turn', '')
                    if target_bar in self.state['bars']:
                        self.state['bars'][target_bar]['current'] += val
                        self.state['bars'][target_bar]['change'] += val
                        
            # 结算 Buff 持续回合
            if bd.get('duration', -1) != -1:
                bd['duration'] -= 1
                if bd['duration'] <= 0: 
                    to_remove.append(bn)
                    
        for b in to_remove: 
            del self.state['buffs'][b]

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
                
        # 6. 结算 NPC 状态
        for k, v in result.get('npc_states', {}).items():
            if isinstance(v, dict): v = ", ".join([f"{dk}:{dv}" for dk, dv in v.items()])
            self.state['npcs'][k] = str(v)
            
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

    def get_dynamic_state(self):
        return { 
            "bars": self.state['bars'], "properties": self.state['properties'], 
            "buffs": self.state['buffs'], "npcs": self.state['npcs'] 
        }