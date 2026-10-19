"""Short schema2 aggregate mutations; no provider calls, timers or UI authority."""
import copy
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .models import CharacterSessionError, canonical_id, json_bytes, MAX_FILE_BYTES
from .limits import MAX_TURNS, MAX_ACTIONS, MAX_ATTEMPTS
from .protocol import V3
from .context_contract import C4
from .group_requests import send_values, batch_values
from .contract import now, parse_result, plan_ledger, reverse_ledger
from .annotations import parse_annotations
from .message_groups import resolve_local_sources
from .group_records import pending_inputs, active_groups, capacity_groups, formal_messages
from .notices import attach_notice

GAP_SECONDS_PER_CHARACTER = 0.1
MIN_GAP_SECONDS = 0.1
MAX_GAP_SECONDS = 3.0


def empty_inverse():
    return {'added_entry_ids': [], 'previous_entries': []}


def busy(session):
    group = next((g for g in active_groups(session) if g['status'] in {'generating', 'delivering'}), None)
    if group:
        return group
    from .legacy_lifecycle import pending_legacy
    pending = pending_legacy(session)
    if pending:
        action, attempt = pending
        return {'group_id': attempt['legacy_execution']['group_id'], 'action_id': action['action_id'],
                'request_id': attempt['request_id'], 'status': 'generating', 'legacy_execution': True,
                'display_mode': attempt['legacy_execution']['display_mode'], 'bubbles': [], 'delivered_count': 0}
    return None


def gap_seconds(body):
    count = sum(not char.isspace() for char in body)
    return max(MIN_GAP_SECONDS, min(MAX_GAP_SECONDS, count * GAP_SECONDS_PER_CHARACTER))


def check_revision(session, revision):
    if type(revision) is not int or revision < 0:
        raise CharacterSessionError('INVALID_REQUEST')
    if session['revision'] != revision:
        raise CharacterSessionError('REVISION_CONFLICT')


def accept_input(session, payload):
    aid, content, note = send_values(payload)
    fingerprint = hashlib.sha256(json_bytes({'content': content, 'ooc_note': note})).hexdigest()
    old = next((a for a in session['requests'] if a['action_id'] == aid), None)
    if old:
        if old['fingerprint'] != fingerprint or old['operation'] != 'send':
            raise CharacterSessionError('IDEMPOTENCY_MISMATCH')
        return old, False
    check_revision(session, payload['expected_revision'])
    from .legacy_lifecycle import pending_legacy
    if pending_legacy(session):
        raise CharacterSessionError('SESSION_BUSY')
    queued = pending_inputs(session)
    if (len(session['requests']) >= MAX_ACTIONS or len(capacity_groups(session)) >= MAX_TURNS
            or len(queued) >= 8 or sum(len(i['message']['content']) for i in queued) + len(content) > 4000
            or sum(len(i.get('ooc_note', '')) for i in queued) + len(note) > 1000):
        raise CharacterSessionError('SESSION_LIMIT')
    timestamp, mid = now(), str(uuid4())
    participants = {p['controller']: p['instance_id'] for p in session['participants']}
    message = {'message_id': mid, 'speaker_instance_id': participants['user'], 'content': content,
               'presentation_mode': session['presentation_mode'], 'visibility': {'audience_instance_ids': list(participants.values())},
               'seq': session['next_seq'], 'created_at': timestamp}
    entry = {'input_id': mid, 'action_id': aid, 'message': message, 'status': 'active'}
    if note:
        entry['ooc_note'] = note
    action = {'action_id': aid, 'operation': 'send', 'fingerprint': fingerprint, 'created_at': timestamp,
              'mode_at_action': session['presentation_mode'], 'result_state': None, 'input_id': mid, 'attempts': []}
    session['inputs'].append(entry); session['requests'].append(action)
    session['next_seq'] += 1; session['revision'] += 1
    from .proactive_contact import on_user_input
    on_user_input(session)
    return action, True


def claim_inputs(session, display_mode='stream', *, explicit=False):
    if display_mode not in {'stream', 'gaps', 'instant'}:
        raise CharacterSessionError('INVALID_REQUEST')
    if busy(session):
        return None
    previous = active_groups(session)
    if previous and previous[-1]['status'] in {'failed', 'cancelled', 'interrupted'} and not explicit:
        return None
    entries = pending_inputs(session)
    if not entries:
        return None
    # A failed in-flight claim can join an already-full later queue. Claim an
    # ordered, bounded prefix rather than deadlocking or dropping old messages.
    bounded, characters, notes = [], 0, 0
    for entry in entries:
        size, note_size = len(entry['message']['content']), len(entry.get('ooc_note', ''))
        if len(bounded) == 8 or characters + size > 4000 or notes + note_size > 1000:
            break
        bounded.append(entry); characters += size; notes += note_size
    entries = bounded
    if not entries:
        raise CharacterSessionError('SESSION_LIMIT')
    if len(capacity_groups(session)) >= MAX_TURNS or sum(len(a['attempts']) for a in session['requests']) >= MAX_ATTEMPTS:
        raise CharacterSessionError('SESSION_LIMIT')
    action = next(a for a in session['requests'] if a['action_id'] == entries[0]['action_id'])
    return create_group(session, action, [i['input_id'] for i in entries], display_mode)


def create_group(session, action, members, display_mode):
    timestamp, gid, rid = now(), str(uuid4()), str(uuid4())
    group = {'group_id': gid, 'action_id': action['action_id'], 'request_id': rid, 'input_ids': members,
             'mode_at_generation': session['presentation_mode'], 'display_mode': display_mode, 'status': 'generating',
             'created_at': timestamp, 'bubbles': [], 'delivered_count': 0, 'next_due_at': None,
             'ledger_plan': [], 'ledger_inverse': empty_inverse()}
    attempt = {'request_id': rid, 'base_revision': session['revision'], 'context_epoch': session['context_epoch'],
               'history_cutoff_seq': session['next_seq'] - 1, 'input_ids': members, 'group_id': gid,
               'reserved_ai_ids': [str(uuid4()) for _ in range(6)], 'reply_contract_id': V3, 'context_contract_id': C4,
               'display_mode': display_mode, 'status': 'pending', 'created_at': timestamp}
    action['attempts'].append(attempt); session['groups'].append(group)
    return copy.deepcopy(attempt)


def current_attempt(session, request_id):
    found = next(((a, t) for a in session['requests'] for t in a['attempts'] if t['request_id'] == request_id), None)
    if found is None:
        raise CharacterSessionError('ACTION_NOT_FOUND')
    action, attempt = found
    group = next((g for g in session['groups'] if g['group_id'] == attempt.get('group_id')), None)
    if group is None:
        raise CharacterSessionError('REPLY_CONTRACT_UNSUPPORTED')
    return action, attempt, group


def prepare_candidate(session, request_id, raw, allowed_messages, projected_entry_ids):
    action, attempt, group = current_attempt(session, request_id)
    if attempt['status'] != 'pending' or group['status'] != 'generating' or attempt['context_epoch'] != session['context_epoch']:
        raise CharacterSessionError('REVISION_CONFLICT')
    base = regeneration_context(session, action) if action['operation'] == 'regenerate' else session
    if action['operation'] == 'regenerate' and any(i['status'] == 'active' and i['message']['seq'] > attempt['history_cutoff_seq'] for i in session['inputs']):
        raise CharacterSessionError('REVISION_CONFLICT')
    formal = formal_messages(base)
    current_inputs = [formal[mid] for mid in group['input_ids'] if mid in formal]
    if len(current_inputs) != len(group['input_ids']):
        raise CharacterSessionError('REVISION_CONFLICT')
    for message in allowed_messages:
        actual = formal.get(message['message_id'])
        if actual != message or message['seq'] > attempt['history_cutoff_seq']:
            raise CharacterSessionError('CONTRACT_INVALID')
    result, _ = resolve_local_sources(parse_result(raw, V3), attempt['reserved_ai_ids'])
    ai = next(p['instance_id'] for p in session['participants'] if p['controller'] == 'ai')
    audience = [p['instance_id'] for p in session['participants']]
    bubbles = [{'ordinal': i, 'message': {'message_id': attempt['reserved_ai_ids'][i], 'speaker_instance_id': ai,
                'content': body['text'], 'presentation_mode': group['mode_at_generation'],
                'visibility': {'audience_instance_ids': audience}}} for i, body in enumerate(result['messages'])]
    messages = {m['message_id']: m for m in [*allowed_messages, *current_inputs, *(b['message'] for b in bubbles)]}
    current_ids = set(group['input_ids']) | {b['message']['message_id'] for b in bubbles}
    planned, inverse = plan_ledger(base, result['ledger_ops'], parse_annotations(result['memory_annotations'], result['ledger_ops']),
                                   messages, current_ids, projected_entry_ids, group['group_id'])
    previous = {e['entry_id']: e for e in inverse['previous_entries']}
    additions = set(inverse['added_entry_ids'])
    plans = []
    for entry in planned['ledger']:
        if entry['entry_id'] in additions:
            item = {'entry': copy.deepcopy(entry)}
            if entry.get('supersedes_entry_id'):
                item['previous_entry'] = previous[entry['supersedes_entry_id']]
            plans.append(item)
    group.update(bubbles=bubbles, generated_at=now(), ledger_plan=plans)
    # Reserve the fully committed aggregate, not only the cheap candidate prefix.
    worst = copy.deepcopy(session)
    if action['operation'] == 'regenerate':
        replace_group(worst, action, group['group_id'])
    wg = next(g for g in worst['groups'] if g['group_id'] == group['group_id'])
    for bubble in wg['bubbles']:
        bubble['message'].update(seq=worst['next_seq'], created_at=now())
        worst['next_seq'] += 1
    wg['delivered_count'] = len(wg['bubbles'])
    settle_ledger(worst, wg)
    if len(json_bytes(worst)) + 1024 > MAX_FILE_BYTES:
        raise CharacterSessionError('SESSION_LIMIT')
    return action, attempt, group


def settle_ledger(session, group):
    inverse = empty_inverse()
    for item in group['ledger_plan']:
        entry = item['entry']
        previous = item.get('previous_entry')
        if previous:
            target = next((e for e in session['ledger'] if e['entry_id'] == previous['entry_id']), None)
            if target != previous:
                raise CharacterSessionError('REVISION_CONFLICT')
            inverse['previous_entries'].append(copy.deepcopy(target))
            target['status'] = 'superseded'
        session['ledger'].append(copy.deepcopy(entry))
        inverse['added_entry_ids'].append(entry['entry_id'])
    group['ledger_inverse'] = inverse
    group['ledger_plan'] = []
    group.update(status='complete', next_due_at=None, settled_at=now(), committed_revision=session['revision'] + 1)
    for aid in {i['action_id'] for i in session['inputs'] if i['input_id'] in group['input_ids']}:
        action = next(a for a in session['requests'] if a['action_id'] == aid)
        action.update(result_state='active', resolved_by_group_id=group['group_id'])
    owner = next(a for a in session['requests'] if a['action_id'] == group['action_id'])
    owner['result_group_id'] = group['group_id']
    if owner['operation'] == 'proactive':
        owner['result_state'] = 'active'
        return
    query = '\n'.join(i['message']['content'] for i in session['inputs'] if i['input_id'] in group['input_ids'])
    attach_notice(session, group, owner, query)


def deliver(session, group, timestamp=None, expected_ordinal=None):
    timestamp = timestamp or datetime.now(timezone.utc)
    if group['status'] not in {'generating', 'delivering'}:
        return False
    if expected_ordinal is not None and group['delivered_count'] != expected_ordinal:
        return False
    if group['status'] == 'delivering' and datetime.fromisoformat(group['next_due_at']) > timestamp:
        return False
    count = 1 if group['display_mode'] == 'gaps' else len(group['bubbles']) - group['delivered_count']
    for bubble in group['bubbles'][group['delivered_count']:group['delivered_count'] + count]:
        bubble['message'].update(seq=session['next_seq'], created_at=timestamp.isoformat())
        session['next_seq'] += 1; group['delivered_count'] += 1
    if group['delivered_count'] == len(group['bubbles']):
        settle_ledger(session, group)
    else:
        body = group['bubbles'][group['delivered_count']]['message']['content']
        group.update(status='delivering', next_due_at=(timestamp + timedelta(seconds=gap_seconds(body))).isoformat())
    session['revision'] += 1
    return True


def commit_generated(session, request_id, raw, allowed_messages, projected_entry_ids, timestamp=None):
    action, attempt, group = prepare_candidate(session, request_id, raw, allowed_messages, projected_entry_ids)
    if action['operation'] == 'regenerate':
        replace_group(session, action, group['group_id'])
    attempt.update(status='committed', ended_at=now())
    deliver(session, group, timestamp)
    attempt['committed_revision'] = session['revision']
    return copy.deepcopy(group)


def commit_proactive_contact(session, plan_id, index, timestamp=None):
    """Internal atomic entry point; the scheduler owns the surrounding save."""
    from .proactive_contact import commit_proactive_contact as commit
    return commit(session, plan_id, index, timestamp)


def fail_generation(session, request_id, status='failed', error_code='PROVIDER_FAILED'):
    from .legacy_lifecycle import execution_for_request, fail_legacy
    if execution_for_request(session, request_id)[1].get('legacy_execution'):
        return fail_legacy(session, request_id, status, error_code)
    _, attempt, group = current_attempt(session, request_id)
    if attempt['status'] != 'pending':
        return False
    if status not in {'failed', 'cancelled', 'interrupted'}:
        raise CharacterSessionError('INVALID_REQUEST')
    attempt.update(status=status, error_code=error_code, ended_at=now())
    group.update(status=status, error_code=error_code, settled_at=now(), bubbles=[], ledger_plan=[], next_due_at=None)
    session['revision'] += 1
    if status == 'cancelled':
        session['context_epoch'] += 1
    return True


def mark_read(session, seq):
    if type(seq) is not int or seq < 0:
        raise CharacterSessionError('INVALID_REQUEST')
    if seq <= session['read_ai_seq']:
        return False
    ai = next(p['instance_id'] for p in session['participants'] if p['controller'] == 'ai')
    maximum = max((m['seq'] for m in formal_messages(session).values() if m['speaker_instance_id'] == ai), default=0)
    if seq > maximum:
        raise CharacterSessionError('INVALID_REQUEST')
    session['read_ai_seq'] = seq; session['revision'] += 1
    return True


def recover_groups(session, timestamp=None):
    """Call once at service start, not GET; never automatically call a provider."""
    timestamp = timestamp or datetime.now(timezone.utc)
    current = busy(session)
    if current is None:
        return False
    if current['status'] == 'generating':
        return fail_generation(session, current['request_id'], 'interrupted', 'PROCESS_INTERRUPTED')
    body = current['bubbles'][current['delivered_count']]['message']['content']
    current['next_due_at'] = (timestamp + timedelta(seconds=gap_seconds(body))).isoformat()
    session['revision'] += 1
    return True


def latest_batch(session, group_id, *, allow_unanswered=False):
    if busy(session):
        raise CharacterSessionError('SESSION_BUSY')
    unresolved = {i['input_id'] for i in pending_inputs(session)}
    completed = [g for g in active_groups(session) if g['status'] == 'complete' or
                 (allow_unanswered and g['status'] in {'failed', 'cancelled', 'interrupted'}
                  and g['input_ids'] and set(g['input_ids']) <= unresolved)]
    if not completed or completed[-1]['group_id'] != group_id:
        raise CharacterSessionError('REVISION_CONFLICT')
    group = completed[-1]
    own = set(group['input_ids'])
    if group['status'] != 'complete' and (not own or not own <= {i['input_id'] for i in pending_inputs(session)}):
        raise CharacterSessionError('REVISION_CONFLICT')
    # Input arriving between A/B bubbles can depend on A even though its seq is
    # less than the final B. The barrier is the claimed input cutoff, not the
    # latest delivered AI sequence.
    if group.get('origin') == 'proactive':
        _, attempt, _ = current_attempt(session, group['request_id'])
        input_cutoff = attempt['history_cutoff_seq']
    else:
        input_cutoff = max(i['message']['seq'] for i in session['inputs'] if i['input_id'] in own)
    if any(i['status'] == 'active' and i['input_id'] not in own and i['message']['seq'] > input_cutoff for i in session['inputs']):
        raise CharacterSessionError('REVISION_CONFLICT')
    return group


def regeneration_context(session, action):
    value = copy.deepcopy(session)
    target = next(g for g in value['groups'] if g['group_id'] == action['target_group_id'])
    if target['status'] != 'complete':
        raise CharacterSessionError('REVISION_CONFLICT')
    reverse_ledger(value, target['ledger_inverse'])
    target['status'] = 'replaced'
    return value


def replace_group(session, action, new_id):
    target = next(g for g in session['groups'] if g['group_id'] == action['target_group_id'])
    if target['status'] != 'complete':
        raise CharacterSessionError('REVISION_CONFLICT')
    reverse_ledger(session, target['ledger_inverse'])
    target.update(status='replaced', replaced_by_group_id=new_id)
    for original in session['requests']:
        if original.get('result_group_id') == target['group_id'] or original.get('resolved_by_group_id') == target['group_id']:
            original['result_state'] = 'replaced'


def batch_action(session, payload, display_mode='stream'):
    aid, gid = batch_values(payload, display_mode)
    fingerprint = hashlib.sha256(json_bytes({'operation': payload['operation'], 'target_group_id': gid})).hexdigest()
    old = next((a for a in session['requests'] if a['action_id'] == aid), None)
    if old:
        if old['fingerprint'] != fingerprint:
            raise CharacterSessionError('IDEMPOTENCY_MISMATCH')
        return old, False
    check_revision(session, payload['expected_revision'])
    target = latest_batch(session, gid, allow_unanswered=payload['operation'] == 'undo')
    if target.get('origin') == 'proactive' and payload['operation'] == 'regenerate':
        raise CharacterSessionError('REPLY_CONTRACT_UNSUPPORTED')
    if len(session['requests']) >= MAX_ACTIONS or sum(len(a['attempts']) for a in session['requests']) >= MAX_ATTEMPTS:
        raise CharacterSessionError('SESSION_LIMIT')
    action = {'action_id': aid, 'operation': payload['operation'], 'fingerprint': fingerprint, 'created_at': now(),
              'mode_at_action': session['presentation_mode'], 'result_state': None, 'target_group_id': gid, 'attempts': []}
    session['requests'].append(action)
    session['context_epoch'] += 1
    session['revision'] += 1
    from .proactive_contact import invalidate
    invalidate(session)
    if action['operation'] == 'regenerate':
        return create_group(session, action, list(target['input_ids']), display_mode), True
    reverse_ledger(session, target['ledger_inverse'])
    target['status'] = 'withdrawn'
    for entry in session['inputs']:
        if entry['input_id'] in target['input_ids']:
            entry['status'] = 'withdrawn'
    for original in session['requests']:
        if original.get('result_group_id') == gid or original.get('resolved_by_group_id') == gid or original.get('input_id') in target['input_ids']:
            original['result_state'] = 'withdrawn'
    action['result_group_id'] = gid
    action['attempts'].append({'request_id': str(uuid4()), 'base_revision': session['revision'] - 1,
                               'status': 'committed', 'created_at': now(), 'ended_at': now(),
                               'committed_revision': session['revision'], 'control_attempt': True})
    return copy.deepcopy(action), True


def retry_group(session, action_id, request_id, retry_token, display_mode='stream'):
    canonical_id(retry_token)
    action = next((a for a in session['requests'] if a['action_id'] == action_id), None)
    if action is None:
        raise CharacterSessionError('ACTION_NOT_FOUND')
    existing = next((a for a in action['attempts'] if a.get('retry_token') == retry_token), None)
    if existing:
        if existing.get('retry_of') != request_id:
            raise CharacterSessionError('IDEMPOTENCY_MISMATCH')
        return copy.deepcopy(existing), False
    previous = require_group_retry(session, action, request_id)
    if display_mode not in {'stream', 'gaps', 'instant'}:
        raise CharacterSessionError('STALE_RETRY')
    created = create_group(session, action, list(previous['input_ids']), display_mode)
    new_attempt = action['attempts'][-1]
    new_attempt.update(retry_of=request_id, retry_token=retry_token)
    return copy.deepcopy(new_attempt), True


def require_group_retry(session, action, request_id):
    """Shared pure eligibility for execution and public retry affordances."""
    if action['operation'] == 'proactive':
        raise CharacterSessionError('STALE_RETRY')
    previous = action['attempts'][-1] if action['attempts'] else None
    if (previous is None or previous['request_id'] != request_id or previous['status'] not in {'failed', 'cancelled', 'interrupted'}
            or previous.get('reply_contract_id') != V3):
        raise CharacterSessionError('STALE_RETRY')
    if busy(session):
        raise CharacterSessionError('SESSION_BUSY')
    unresolved = {i['input_id'] for i in pending_inputs(session)}
    if action['operation'] == 'regenerate':
        latest_batch(session, action['target_group_id'])
    elif not set(previous['input_ids']) <= unresolved:
        raise CharacterSessionError('STALE_RETRY')
    occupied = len(capacity_groups(session)) - (1 if action['operation'] == 'regenerate' else 0)
    if sum(len(a['attempts']) for a in session['requests']) >= MAX_ATTEMPTS or occupied >= MAX_TURNS:
        raise CharacterSessionError('SESSION_LIMIT')
    return previous
