import json
import re


def response(kind, user):
    pattern = r'【玩家行动】\n([^\n]*)' if kind == 'worldbook_capture' else r'【行动】：([^\n]*)'
    action = re.search(pattern, user)
    if not action or '【AW_BOOK:' not in action.group(1):
        return None
    tag = re.search(r'【AW_BOOK:([^】]+)】', action.group(1)).group(1)
    if kind == 'reaction':
        return {'reactions': [{'description': '设定验收继续', 'weight': 1}]}
    if kind == 'settlement':
        story = f'设定验收{tag}：法令已确认生效。'
        change = {'update': 'update', 'retire': 'expire'}.get(tag, 'add')
        return {'story_text': story, 'world_change_events': [{'summary': '设定验收', 'fact_status': 'confirmed',
            'change_kind': change, 'scope_hint': 'organization', 'time_hint': 'persistent', 'evidence': story}]}
    if kind != 'worldbook_capture':
        return None
    catalog_match = re.search(r'【世界书目录】\n([^\n]*)', user)
    catalog = json.loads(catalog_match.group(1)) if catalog_match else []
    book = next((b for b in catalog if not b.get('is_auto_capture_book')), catalog[0] if catalog else None)
    if book is None:
        book = json.loads(re.search(r'【当前世界书】\n([^\n]*)', user).group(1))
    candidate = {'name': '验收法令', 'content': '蓝灯时通行', 'keys': '法令', 'scope': 'social_system',
                 'confidence': 'high', 'risk': 'low', 'event_index': 0}
    if catalog:
        candidate['target_book_id'] = book['book_id']
    if tag == 'routing':
        return {'candidates': [{**candidate, 'target_book_id': target, 'name': name, 'content': content}
            for target, name, content in [('归属主书', '基础法令', '此地区法令长期有效'),
                                         ('归属知识书', '通用技法', '此技法适用于所有学徒'),
                                         ('', '交叉设定', '跨体系的长期规则')]]}
    if tag in ('update', 'retire'):
        candidate.update(operation=tag, target_entry_id=next(e['id'] for e in book['entries'] if e['name'] == '验收法令'), content='绿灯时通行')
    if tag == 'manual':
        return {'candidates': [{**candidate, 'name': f'候选{i}', 'content': f'候选法令{i}'} for i in (1, 2)]}
    return {'candidates': [candidate]}
