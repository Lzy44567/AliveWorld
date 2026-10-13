"""Scene identity acceptance fixtures driven by the actual request context."""
import json
import re


def response(kind, user):
    action = re.search(r'【行动】：([^\n]*)', user)
    if not action or '【AW_NPC:' not in action.group(1):
        return None
    tag = re.search(r'【AW_NPC:([^】]+)】', action.group(1)).group(1)
    if kind == 'reaction':
        return {'reactions': [{'description': '依照当前人物身份继续', 'weight': 1}]}
    if kind != 'settlement':
        return None
    if tag == 'init':
        return {'story_text': '人物验收：看守在门口。', 'npc_states': {'看守': '在门口'}, 'worldbook_capture_needed': False}
    match = re.search(r'【本局已知人物身份】：([^\n]*)', user)
    identities = json.loads(match.group(1)) if match else []
    person = next((p for p in identities if p['name'] in ('看守', '阿林')), None)
    if not person:
        return '{missing required identity context'
    operation = {'name': '阿林', 'id': person['id'], 'reason': '本回合明确介绍或出入场'}
    result = {'story_text': f'人物验收：{tag}，阿林。', 'worldbook_capture_needed': False}
    if tag == 'mention':
        result['npc_states'] = {'看守': '在旧门口（只是回忆）'}
    else:
        operation['present'] = tag != 'leave'
        if tag == 'conflict':
            operation['id'] = 'nonexistent'
        result['npc_identity_updates'] = [operation]
        if tag != 'leave':
            result['npc_states'] = {'阿林': '害怕死亡，但仍在现场'}
    return result
