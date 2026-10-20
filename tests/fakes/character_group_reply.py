"""Deterministic C4-only fixture; old character contracts stay independent."""
import json


def response(data):
    if data.get('context_contract_id') != 'character.context.c4.v1':
        raise ValueError('Unknown group test context')
    inputs = data.get('current_user_messages')
    if not isinstance(inputs, list) or not inputs:
        raise ValueError('Missing group inputs')
    content = ' / '.join(m['content'] for m in inputs)
    mode = data.get('presentation_mode', 'messenger')
    result = {'messages': [
        {'local_id': 'b0', 'text': f'多气泡验收（{mode}）：{content}'},
        {'local_id': 'b1', 'text': '这是同一次请求的第二条消息。'},
    ], 'ledger_ops': [], 'memory_annotations': []}
    if '【C4单句】' in content:
        result['messages'] = [{'local_id': 'b0', 'text': '好，六点见。'}]
    if '【C4坏JSON】' in content:
        return json.dumps(result, ensure_ascii=False) + ' trailing'
    return result
