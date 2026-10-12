"""Echo program-calculated effects; fixtures never calculate the tested damage."""
import json
import re


def response(kind, user):
    action = re.search(r'【行动】：([^\n]*)', user)
    if not action or '【AW_EFFECT:' not in action.group(1):
        return None
    tag = re.search(r'【AW_EFFECT:([^】]+)】', action.group(1)).group(1)
    if kind == 'reaction':
        candidate = {'id': 1, 'description': '遵守当前效果与经过时间', 'weight': 1}
        if not tag.startswith('init'):
            mode, amount = ('seconds', 2592000) if tag == 'month' else ('seconds', 10)
            if ':' in tag:
                mode, value = tag.split(':')
                amount = int(value)
            candidate['effect_progress'] = {'mode': mode, 'amount': amount, 'reason': '固定验收时间计划', 'stop_at_zero': ['生命']}
        return {'reactions': [candidate], 'influence_checks': []}
    if kind != 'settlement':
        return None
    if tag == 'bad':
        return '{invalid json'
    if tag.startswith('init'):
        return {
            'story_text': '效果验收开场：尚未经过毒伤结算时间。',
            'dynamic_bars': {'生命': {'current': 8 if tag == 'init-critical' else 100, 'max': 100}},
            'new_buffs': {'中毒测试': {'生命_per_turn': -5, 'duration': 5, 'tick_seconds': 10, 'description': '每十秒损失5点生命'}},
            'worldbook_capture_needed': False,
        }
    state = json.loads(re.search(r'【状态】：([^\n]*)', user).group(1))
    report = json.loads(re.search(r'【runtime.effect_progress 程序结算报告】：([^\n]*)', user).group(1))
    return {
        'story_text': f"效果验收：程序生命值{state['bars']['生命']['current']}；实际推进{report['applied']}；中断{report['interrupted']}。",
        'worldbook_capture_needed': False,
    }
