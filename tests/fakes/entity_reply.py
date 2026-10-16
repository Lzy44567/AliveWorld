import re


def response(kind, user):
    pattern = r'"player_action":\s*"【AW_ENTITY:(\w+)】' if kind == 'overseer' else r'【行动】：【AW_ENTITY:(\w+)】'
    match = re.search(pattern, user)
    if not match:
        return None
    tag = match.group(1)
    if kind == 'reaction':
        return {'reactions': [{'description': '实体验收', 'weight': 1}]}
    if kind == 'settlement':
        return {'story_text': f'实体验收{tag}。玩家在旅馆，没有获知商会的秘密。',
                'status_updates': {'当前时间': '第一日午后'}}
    if kind != 'overseer':
        return None
    name = '新商会' if '【新商会】' in user else '验收商会'
    if tag == 'dead':
        return {'delete_entities': [name]}
    event = {'entity': name, 'kind': 'plan' if tag == 'plan' else 'action',
             'action': '计划运输药材' if tag == 'plan' else '已派出药材车队',
             'basis': '商会收到订单并拥有一辆车', 'known_to': [name]}
    influences = [] if tag == 'plan' else [{'id': 'shipment-e2e', 'summary': '药材车队运输中',
        'source_links': [{'entity': name, 'on_source_death': 'keep'}],
        'condition': '玩家抵达远方码头', 'effect': '看见车队'}]
    return {'undercurrent_events': [event], 'new_influences': influences}
