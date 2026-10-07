"""Explicit old-protocol executions without premature formal messages."""
import copy
from uuid import uuid4

from .models import CharacterSessionError, canonical_id, json_bytes, MAX_FILE_BYTES
from .limits import MAX_ATTEMPTS, MAX_TURNS
from .contract import now, parse_result, plan_ledger, reverse_ledger
from .protocol import V2
from .annotations import parse_annotations
from .legacy_context import legacy_snapshot
from .group_records import active_groups, pending_inputs, capacity_groups, formal_messages
from .memory import select_memory, public


def pending_legacy(session):
    return next(((a, t) for a in session['requests'] for t in a['attempts']
                 if t.get('legacy_execution') and t['status'] == 'pending'), None)


def execution_for_request(session, rid):
    found = next(((a, t) for a in session['requests'] for t in a['attempts'] if t['request_id'] == rid), None)
    if found is None:
        raise CharacterSessionError('ACTION_NOT_FOUND')
    action, attempt = found
    if attempt.get('legacy_execution'):
        return action, attempt, attempt['legacy_execution']
    group = next((g for g in session['groups'] if g['group_id'] == attempt.get('group_id')), None)
    if group is None:
        raise CharacterSessionError('REPLY_CONTRACT_UNSUPPORTED')
    return action, attempt, group


def _eligible(session, action):
    if action.get('result_state') is not None or action.get('result_group_id') or pending_inputs(session):
        raise CharacterSessionError('STALE_RETRY')
    index = session['requests'].index(action)
    if any(a.get('input_id') or a.get('result_group_id') for a in session['requests'][index + 1:]):
        raise CharacterSessionError('STALE_RETRY')
    if action['operation'] == 'regenerate':
        complete = [g for g in active_groups(session) if g['status'] == 'complete']
        if not complete or complete[-1]['group_id'] != action.get('target_group_id'):
            raise CharacterSessionError('STALE_RETRY')
        target = complete[-1]
        cutoff = max(i['message']['seq'] for i in session['inputs'] if i['input_id'] in target['input_ids'])
        if any(i['status'] == 'active' and i['input_id'] not in target['input_ids']
               and i['message']['seq'] > cutoff for i in session['inputs']):
            raise CharacterSessionError('STALE_RETRY')
    elif action['operation'] != 'send':
        raise CharacterSessionError('STALE_RETRY')


def begin_legacy_retry(session, action_id, retry_of, retry_token, display_mode='stream'):
    canonical_id(action_id); canonical_id(retry_of); canonical_id(retry_token)
    if display_mode not in {'stream', 'gaps', 'instant'}:
        raise CharacterSessionError('INVALID_REQUEST')
    action = next((a for a in session['requests'] if a['action_id'] == action_id), None)
    if not action:
        raise CharacterSessionError('ACTION_NOT_FOUND')
    for attempt in action['attempts']:
        if attempt.get('retry_token') == retry_token:
            if attempt.get('retry_of') != retry_of:
                raise CharacterSessionError('IDEMPOTENCY_MISMATCH')
            return copy.deepcopy(attempt), False
    snapshot, contract, context = require_legacy_retry(session, action, retry_of)
    attempt = {'request_id': str(uuid4()), 'base_revision': session['revision'], 'status': 'pending',
               'created_at': now(), 'legacy_attempt': True, 'reply_contract_id': contract,
               'context_contract_id': context, 'retry_of': retry_of, 'retry_token': retry_token,
               'legacy_retry_snapshot': copy.deepcopy(snapshot),
               'legacy_execution': {'group_id': str(uuid4()), 'context_epoch': session['context_epoch'],
                                    'history_cutoff_seq': session['next_seq'] - 1, 'display_mode': display_mode}}
    action['legacy_retry_snapshot'] = snapshot
    action['attempts'].append(attempt)
    return copy.deepcopy(attempt), True


def require_legacy_retry(session, action, retry_of):
    if pending_legacy(session) or any(g['status'] in {'generating', 'delivering'} for g in active_groups(session)):
        raise CharacterSessionError('SESSION_BUSY')
    previous = action['attempts'][-1] if action['attempts'] else {}
    if previous.get('request_id') != retry_of or previous.get('status') not in {'failed', 'cancelled', 'interrupted'}:
        raise CharacterSessionError('STALE_RETRY')
    snapshot, contract, context = legacy_snapshot(action, previous)
    _eligible(session, action)
    count = len(capacity_groups(session)) - (action['operation'] == 'regenerate')
    if count >= MAX_TURNS or sum(len(a['attempts']) for a in session['requests']) >= MAX_ATTEMPTS:
        raise CharacterSessionError('SESSION_LIMIT')
    return snapshot, contract, context


def fail_legacy(session, rid, status='failed', error_code='PROVIDER_FAILED'):
    _, attempt, _ = execution_for_request(session, rid)
    if not attempt.get('legacy_execution'):
        raise CharacterSessionError('REPLY_CONTRACT_UNSUPPORTED')
    if attempt['status'] != 'pending':
        return False
    if status not in {'failed', 'cancelled', 'interrupted'}:
        raise CharacterSessionError('INVALID_REQUEST')
    attempt.update(status=status, error_code=error_code, ended_at=now())
    session['revision'] += 1
    if status == 'cancelled':
        session['context_epoch'] += 1
    return True


def commit_legacy(session, rid, raw, allowed_messages, projected_entry_ids):
    action, attempt, execution = execution_for_request(session, rid)
    if (not attempt.get('legacy_execution') or attempt['status'] != 'pending'
            or action['attempts'][-1] is not attempt or execution['context_epoch'] != session['context_epoch']
            or execution['history_cutoff_seq'] != session['next_seq'] - 1):
        raise CharacterSessionError('REVISION_CONFLICT')
    _eligible(session, action)
    snapshot, contract, _ = legacy_snapshot(action, attempt)
    candidate = copy.deepcopy(session)
    target = None
    if action['operation'] == 'regenerate':
        target = next(g for g in candidate['groups'] if g['group_id'] == action['target_group_id'])
        reverse_ledger(candidate, target['ledger_inverse'])
        target.update(status='replaced', replaced_by_group_id=execution['group_id'])
        for entry in candidate['inputs']:
            if entry['input_id'] in target['input_ids']:
                entry['status'] = 'withdrawn'
        for original in candidate['requests']:
            if original.get('result_group_id') == target['group_id'] or original.get('resolved_by_group_id') == target['group_id']:
                original['result_state'] = 'replaced'
    formal = formal_messages(candidate)
    for message in allowed_messages:
        actual = formal.get(message.get('message_id'))
        if actual is None or any(message.get(k) != actual.get(k) for k in
                                 ('message_id', 'turn_id', 'speaker_instance_id', 'content', 'visibility')):
            raise CharacterSessionError('CONTRACT_INVALID')
    result = parse_result(raw, contract)
    ids = {p['controller']: p['instance_id'] for p in candidate['participants']}
    timestamp = now()
    def message(mid, speaker, content, seq):
        return {'message_id': mid, 'speaker_instance_id': ids[speaker], 'content': content,
                'presentation_mode': snapshot['mode'], 'visibility': {'audience_instance_ids': list(ids.values())},
                'created_at': timestamp, 'seq': seq}
    user = message(snapshot['user_message_id'], 'user', snapshot['content'], candidate['next_seq'])
    reply = message(snapshot['ai_message_id'], 'ai', result['reply'], candidate['next_seq'] + 1)
    messages = {m['message_id']: m for m in [*allowed_messages, user, reply]}
    annotations = parse_annotations(result['memory_annotations'], result['ledger_ops']) if contract == V2 else {}
    candidate, inverse = plan_ledger(candidate, result['ledger_ops'], annotations, messages,
                                     {user['message_id'], reply['message_id']}, projected_entry_ids, execution['group_id'])
    entry = {'input_id': user['message_id'], 'action_id': action['action_id'], 'message': user, 'status': 'active'}
    if snapshot.get('ooc_note'):
        entry['ooc_note'] = snapshot['ooc_note']
    candidate['inputs'].append(entry)
    group = {'group_id': execution['group_id'], 'action_id': action['action_id'], 'request_id': rid,
             'input_ids': [user['message_id']], 'mode_at_generation': snapshot['mode'],
             'display_mode': execution['display_mode'], 'status': 'complete', 'created_at': timestamp,
             'generated_at': timestamp, 'settled_at': timestamp, 'bubbles': [{'ordinal': 0, 'message': reply}],
             'delivered_count': 1, 'next_due_at': None, 'ledger_plan': [], 'ledger_inverse': inverse,
             'committed_revision': session['revision'] + 1}
    candidate['groups'].append(group)
    candidate['next_seq'] += 2
    candidate['revision'] += 1
    owner = next(a for a in candidate['requests'] if a['action_id'] == action['action_id'])
    owner.update(input_id=user['message_id'], result_group_id=group['group_id'], resolved_by_group_id=group['group_id'], result_state='active')
    owner.pop('legacy_retry_snapshot', None)
    saved_attempt = owner['attempts'][-1]
    saved_attempt.update(status='committed', ended_at=timestamp, committed_revision=candidate['revision'])
    if annotations and action['operation'] == 'send':
        _, report = select_memory(candidate, snapshot['content'])
        selected = {e['entry_id'] for e in report if e['reason'] in {'auto_important', 'auto_highlight'}}
        notice = [e['entry_id'] for e in candidate['ledger'] if e['entry_id'] in inverse['added_entry_ids']
                  and e['entry_id'] in selected and not e.get('supersedes_entry_id') and public(e, candidate)]
        if notice:
            group['memory_notice'] = {'action_id': action['action_id'], 'committed_revision': candidate['revision'], 'entry_ids': notice}
    if len(json_bytes(candidate)) + 1024 > MAX_FILE_BYTES:
        raise CharacterSessionError('SESSION_LIMIT')
    from .group_schema import validate_schema2
    validate_schema2(candidate)
    session.clear(); session.update(candidate)
    return copy.deepcopy(group)
