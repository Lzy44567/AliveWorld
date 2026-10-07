"""Pure, deterministic schema1 conversion. Never opens or replaces player files."""
import copy

from .models import CharacterSessionError, validate_session
from .group_schema import validate_schema2


def convert_legacy_session(original):
    if not isinstance(original, dict):
        raise CharacterSessionError('SESSION_CORRUPT')
    if original.get('schema_version') == 2:
        validate_schema2(original)
        return copy.deepcopy(original)
    validate_session(original)
    if original.get('deleted'):
        return {'schema_version': 2, 'session_id': original['session_id'], 'deleted': True}
    result = copy.deepcopy(original)
    result.pop('turns')
    result.update(schema_version=2, context_epoch=0, next_seq=1, read_ai_seq=0, inputs=[], groups=[])
    inputs = {}
    active = {t['turn_id'] for t in original['turns']}
    records = list(original['turns']) + [a['archived_turn'] for a in original['requests'] if a.get('archived_turn')]
    old_actions = {a['action_id']: a for a in original['requests']}
    for turn in records:
        current = turn['turn_id'] in active
        user = copy.deepcopy(turn['user_message'])
        previous = inputs.get(user['message_id'])
        if previous:
            comparable = dict(previous['message']); comparable.pop('seq')
            if comparable != user or previous.get('ooc_note', '') != turn.get('ooc_note', ''):
                raise CharacterSessionError('SESSION_CORRUPT')
            if current:
                previous['status'] = 'active'
        else:
            user['seq'] = result['next_seq']; result['next_seq'] += 1
            entry = {'input_id': user['message_id'], 'action_id': turn['action_id'], 'message': user,
                     'status': 'active' if current else 'withdrawn'}
            if turn.get('ooc_note'):
                entry['ooc_note'] = turn['ooc_note']
            inputs[user['message_id']] = entry
            result['inputs'].append(entry)
        ai = copy.deepcopy(turn['ai_message'])
        ai['seq'] = result['next_seq']; result['next_seq'] += 1
        old_action = old_actions[turn['action_id']]
        status = 'complete' if current else old_action.get('result_state')
        if status not in {'complete', 'withdrawn', 'replaced'}:
            raise CharacterSessionError('SESSION_CORRUPT')
        group = {'group_id': turn['turn_id'], 'action_id': turn['action_id'], 'request_id': turn['request_id'],
                 'input_ids': [user['message_id']], 'mode_at_generation': turn['mode_at_generation'],
                 'display_mode': 'instant', 'status': status, 'created_at': turn['created_at'],
                 'generated_at': turn['created_at'], 'settled_at': turn['created_at'],
                 'bubbles': [{'ordinal': 0, 'message': ai}], 'delivered_count': 1,
                 'next_due_at': None, 'ledger_plan': [], 'ledger_inverse': copy.deepcopy(turn['ledger_inverse']),
                 'committed_revision': turn['committed_revision']}
        if turn.get('memory_notice'):
            group['memory_notice'] = copy.deepcopy(turn['memory_notice'])
        result['groups'].append(group)
        if current:
            result['read_ai_seq'] = max(result['read_ai_seq'], ai['seq'])
    for action in result['requests']:
        action.pop('archived_turn', None)
        if 'target_turn_id' in action:
            action['target_group_id'] = action.pop('target_turn_id')
        if 'result_turn_id' in action:
            action['result_group_id'] = action.pop('result_turn_id')
        matching = [i for i in result['inputs'] if i['action_id'] == action['action_id']]
        if action['operation'] in {'send', 'regenerate'} and matching:
            action['input_id'] = matching[0]['input_id']
        if 'retry_input' in action:
            action['legacy_retry_snapshot'] = action.pop('retry_input')
        for attempt in action['attempts']:
            attempt['legacy_attempt'] = True
            if 'pending_input' in attempt:
                attempt['legacy_retry_snapshot'] = attempt.pop('pending_input')
            if attempt['status'] == 'pending':
                attempt['status'] = 'interrupted'
                attempt['error_code'] = 'PROCESS_INTERRUPTED'
                attempt['ended_at'] = original['updated_at']
    validate_schema2(result)
    return result
