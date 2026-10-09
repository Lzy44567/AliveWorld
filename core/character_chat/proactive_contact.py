"""Session-owned finite contact cycles; no provider or scheduling authority."""
import copy
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .models import CharacterSessionError, canonical_id, json_bytes
from .limits import MAX_ACTIONS, MAX_ATTEMPTS, MAX_TURNS, MAX_EXTENSIONS_BYTES
from .contract import now

DEFAULTS = {'enabled': False, 'idle_seconds': 600, 'max_contacts': 2, 'paused': False,
            'authorization_revision': 0, 'interaction_epoch': 0, 'cycle_state': 'idle', 'plan': None}
SETTING_KEYS = {'enabled', 'idle_seconds', 'max_contacts', 'paused'}
CYCLE_STATES = {'idle', 'armed', 'planning', 'planned', 'exhausted'}


def state(session):
    return session['extensions'].get('proactive_contact', DEFAULTS)


def settings(session):
    value = state(session)
    public = {key: value[key] for key in DEFAULTS if key != 'plan'}
    plan = value['plan']
    public.update(next_due_at=None, expires_at=plan['expires_at'] if plan else None)
    if plan and value['cycle_state'] == 'planned' and plan['next_index'] < len(plan['contacts']):
        delay = plan['contacts'][plan['next_index']]['delay_seconds']
        public['next_due_at'] = (datetime.fromisoformat(plan['planned_at']) + timedelta(seconds=delay)).isoformat()
    return public


def configure(session, expected_revision, patch):
    from .group_lifecycle import check_revision
    if not isinstance(patch, dict) or not patch or not set(patch) <= SETTING_KEYS:
        raise CharacterSessionError('INVALID_REQUEST')
    for key in ('enabled', 'paused'):
        if key in patch and type(patch[key]) is not bool:
            raise CharacterSessionError('INVALID_REQUEST')
    for key, low, high in (('idle_seconds', 1, 7200), ('max_contacts', 1, 5)):
        if key in patch and (type(patch[key]) is not int or not low <= patch[key] <= high):
            raise CharacterSessionError('INVALID_REQUEST')
    check_revision(session, expected_revision)
    value = copy.deepcopy(state(session))
    value.update(patch)
    value.update(authorization_revision=value['authorization_revision'] + 1, cycle_state='idle', plan=None)
    session['extensions']['proactive_contact'] = value
    session['revision'] += 1
    return settings(session)


def on_user_input(session):
    # Old schema2 files remain byte-for-byte extension compatible while disabled.
    if 'proactive_contact' not in session['extensions']:
        return False
    value = state(session)
    value.update(interaction_epoch=value['interaction_epoch'] + 1, plan=None,
                 cycle_state='armed' if value['enabled'] and not value['paused'] else 'idle')
    return True


def invalidate(session):
    if 'proactive_contact' not in session['extensions']:
        return False
    value = state(session)
    changed = value['plan'] is not None or value['cycle_state'] != 'idle'
    value.update(plan=None, cycle_state='idle')
    return changed


def finish_cycle(session, state='exhausted'):
    value = session['extensions'].get('proactive_contact')
    if value is None:
        return False
    value.update(plan=None, cycle_state=state)
    session['revision'] += 1
    return True


def mark_planning(session, plan_id, quota_day, expires_at, max_contacts, timestamp=None,
                  *, allowed_message_ids=(), allowed_entry_ids=()):
    value = state(session)
    if not value['enabled'] or value['paused'] or value['cycle_state'] != 'armed':
        return None
    canonical_id(plan_id)
    timestamp = timestamp or datetime.now(timezone.utc)
    plan = {'plan_id': plan_id, 'interaction_epoch': value['interaction_epoch'],
            'authorization_revision': value['authorization_revision'], 'context_epoch': session['context_epoch'],
            'history_cutoff_seq': session['next_seq'] - 1, 'quota_day': quota_day,
            'expires_at': expires_at.isoformat() if isinstance(expires_at, datetime) else expires_at,
            'planned_at': timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
            'contacts': [], 'next_index': 0, 'allowed_message_ids': list(allowed_message_ids),
            'allowed_entry_ids': list(allowed_entry_ids),
            'reservations': [{'group_id': str(uuid4()), 'action_id': str(uuid4()), 'request_id': str(uuid4()),
                              'reserved_ai_ids': [str(uuid4()) for _ in range(6)]} for _ in range(max_contacts)]}
    value.update(cycle_state='planning', plan=plan)
    session['revision'] += 1
    return copy.deepcopy(plan)


def plan_current(session, plan_id):
    value = state(session)
    plan = value['plan']
    return (plan if plan and plan['plan_id'] == plan_id and value['enabled'] and not value['paused']
            and plan['interaction_epoch'] == value['interaction_epoch']
            and plan['authorization_revision'] == value['authorization_revision']
            and plan['context_epoch'] == session['context_epoch'] else None)


def validate_stored(session):
    """File boundary validation, without injecting defaults into old records."""
    from .group_schema import fields, integer, timestamp, corrupt
    from .contract import parse_result
    from .protocol import V3
    value = session['extensions'].get('proactive_contact')
    if value is None:
        return
    fields(value, set(DEFAULTS))
    if type(value['enabled']) is not bool or type(value['paused']) is not bool:
        corrupt()
    integer(value['idle_seconds'], 1, 7200)
    integer(value['max_contacts'], 1, 5)
    integer(value['authorization_revision'])
    integer(value['interaction_epoch'])
    if value['cycle_state'] not in CYCLE_STATES:
        corrupt()
    plan = value['plan']
    if plan is None:
        if value['cycle_state'] in {'planning', 'planned'}:
            corrupt()
        return
    fields(plan, {'plan_id', 'interaction_epoch', 'authorization_revision', 'context_epoch', 'history_cutoff_seq',
                  'quota_day', 'expires_at', 'planned_at', 'contacts', 'next_index',
                  'allowed_message_ids', 'allowed_entry_ids'}, {'reservations'})
    canonical_id(plan['plan_id'])
    for key in ('interaction_epoch', 'authorization_revision'):
        if plan[key] != value[key]:
            corrupt()
    integer(plan['context_epoch'], 0, session['context_epoch'])
    integer(plan['history_cutoff_seq'], 0, session['next_seq'] - 1)
    timestamp(plan['expires_at']); timestamp(plan['planned_at'])
    datetime.strptime(plan['quota_day'], '%Y-%m-%d')
    for key in ('allowed_message_ids', 'allowed_entry_ids'):
        ids = plan[key]
        if not isinstance(ids, list) or len(ids) != len(set(ids)):
            corrupt()
        for identifier in ids:
            canonical_id(identifier)
    if not isinstance(plan['contacts'], list) or len(plan['contacts']) > value['max_contacts']:
        corrupt()
    integer(plan['next_index'], 0, len(plan['contacts']))
    reservations = plan.get('reservations', [])
    if value['cycle_state'] == 'planning':
        if plan['contacts'] or plan['next_index'] or not isinstance(reservations, list) or not 1 <= len(reservations) <= value['max_contacts']:
            corrupt()
    elif value['cycle_state'] != 'planned' or reservations or not plan['contacts'] or plan['next_index'] == len(plan['contacts']):
        corrupt()
    total, delay, identities = 0, -1, set()
    for index, contact in enumerate(plan['contacts']):
        fields(contact, {'group_id', 'action_id', 'request_id', 'reserved_ai_ids', 'delay_seconds', 'reply'})
        integer(contact['delay_seconds'], 0, 7200)
        if contact['delay_seconds'] < delay:
            corrupt()
        delay = contact['delay_seconds']
        if index < plan['next_index']:
            if contact['reply'] != '':
                corrupt()
        else:
            reply = parse_result(contact['reply'], V3)
            total += sum(len(m['text']) for m in reply['messages'])
    for contact in [*reservations, *plan['contacts']]:
        if contact in reservations:
            fields(contact, {'group_id', 'action_id', 'request_id', 'reserved_ai_ids'})
        ids = contact['reserved_ai_ids']
        if not isinstance(ids, list) or len(ids) != 6:
            corrupt()
        for identifier in [contact['group_id'], contact['action_id'], contact['request_id'], *ids]:
            canonical_id(identifier)
            if identifier in identities:
                corrupt()
            identities.add(identifier)
    if total > 8000:
        corrupt()


def save_plan(session, plan_id, parsed_contacts, timestamp=None):
    plan = plan_current(session, plan_id)
    if plan is None or state(session)['cycle_state'] != 'planning':
        return False
    if len(parsed_contacts) > len(plan['reservations']):
        raise CharacterSessionError('CONTRACT_INVALID')
    total = sum(len(m['text']) for c in parsed_contacts for m in c['reply']['messages'])
    if total > 8000:
        raise CharacterSessionError('CONTRACT_INVALID')
    candidate = copy.deepcopy(state(session))
    saved = candidate['plan']
    saved['planned_at'] = (timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp) or now()
    saved['contacts'] = [dict(reserved, delay_seconds=contact['delay_seconds'],
                              reply=json.dumps(contact['reply'], ensure_ascii=False, separators=(',', ':')))
                         for reserved, contact in zip(saved.pop('reservations'), parsed_contacts)]
    candidate['cycle_state'] = 'planned' if parsed_contacts else 'exhausted'
    if not parsed_contacts:
        candidate['plan'] = None
    extensions = dict(session['extensions'], proactive_contact=candidate)
    if len(json_bytes(extensions)) > MAX_EXTENSIONS_BYTES:
        raise CharacterSessionError('SESSION_LIMIT')
    session['extensions']['proactive_contact'] = candidate
    session['revision'] += 1
    return True


def commit_proactive_contact(session, plan_id, index, timestamp=None):
    from .group_lifecycle import busy, commit_generated, empty_inverse
    from .group_records import capacity_groups, formal_messages, pending_inputs
    from .protocol import V3
    from .context_contract import C4
    existing = next((g for g in session['groups'] if g.get('contact_ref') == {'plan_id': plan_id, 'index': index}), None)
    if existing:
        return copy.deepcopy(existing)
    plan = plan_current(session, plan_id)
    if plan is None or state(session)['cycle_state'] != 'planned' or index != plan['next_index']:
        return None
    if busy(session) or pending_inputs(session):
        return None
    timestamp = timestamp or datetime.now(timezone.utc)
    if datetime.fromisoformat(plan['expires_at']) <= timestamp:
        invalidate(session)
        session['revision'] += 1
        return None
    contact = plan['contacts'][index]
    due = datetime.fromisoformat(plan['planned_at']) + timedelta(seconds=contact['delay_seconds'])
    if timestamp < due:
        return None
    if (len(session['requests']) >= MAX_ACTIONS or len(capacity_groups(session)) >= MAX_TURNS
            or sum(len(a['attempts']) for a in session['requests']) >= MAX_ATTEMPTS):
        raise CharacterSessionError('SESSION_LIMIT')
    created_at = timestamp.isoformat()
    group = {'group_id': contact['group_id'], 'action_id': contact['action_id'], 'request_id': contact['request_id'],
             'input_ids': [], 'origin': 'proactive', 'contact_ref': {'plan_id': plan_id, 'index': index},
             'mode_at_generation': session['presentation_mode'], 'display_mode': 'instant', 'status': 'generating',
             'created_at': created_at, 'bubbles': [], 'delivered_count': 0, 'next_due_at': None,
             'ledger_plan': [], 'ledger_inverse': empty_inverse()}
    attempt = {'request_id': contact['request_id'], 'base_revision': session['revision'],
               'context_epoch': plan['context_epoch'], 'history_cutoff_seq': plan['history_cutoff_seq'],
               'input_ids': [], 'group_id': contact['group_id'], 'reserved_ai_ids': contact['reserved_ai_ids'],
               'reply_contract_id': V3, 'context_contract_id': C4, 'display_mode': 'instant',
               'status': 'pending', 'created_at': created_at}
    action = {'action_id': contact['action_id'], 'operation': 'proactive', 'fingerprint': plan_id,
              'created_at': created_at, 'mode_at_action': session['presentation_mode'], 'result_state': None,
              'attempts': [attempt]}
    formal = formal_messages(session)
    allowed = [formal[mid] for mid in plan['allowed_message_ids'] if mid in formal]
    if len(allowed) != len(plan['allowed_message_ids']):
        raise CharacterSessionError('REVISION_CONFLICT')
    session['groups'].append(group)
    session['requests'].append(action)
    committed = commit_generated(session, attempt['request_id'], contact['reply'], allowed, set(plan['allowed_entry_ids']), timestamp)
    plan['next_index'] += 1
    # Release delivered candidate text immediately, even when later timers remain.
    contact['reply'] = ''
    if plan['next_index'] == len(plan['contacts']):
        state(session).update(plan=None, cycle_state='exhausted')
    return committed
