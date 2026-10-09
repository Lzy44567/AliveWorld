"""Strict schema2 validation, deliberately not enabled in the live repository yet."""
from datetime import datetime, timedelta
from .models import (CharacterSessionError, canonical_id, json_bytes, text, validate_depth,
                     validate_envelope, MAX_FILE_BYTES)
from .limits import MAX_TURNS, MAX_ACTIONS, MAX_ATTEMPTS, MAX_LEDGER, MAX_ACTIVE
from .protocol import V1, V2, V3, validate_contract
from .context_contract import LEGACY, C3, C4, validate_context_contract
from .annotations import validate_annotation
from .opening import validate_opening
from .notices import validate_notice
from .ooc import validate_stored_ooc
from .group_records import CURRENT_GROUP_STATES, capacity_groups, pending_inputs, formal_messages as current_messages


def corrupt():
    raise CharacterSessionError('SESSION_CORRUPT')


def integer(value, minimum=0, maximum=None):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        corrupt()
    return value


def fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or not set(value) <= set(required) | set(optional):
        corrupt()


def timestamp(value):
    text(value, 64)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        corrupt()


def validate_schema2(value):
    try:
        _validate(value)
    except CharacterSessionError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, StopIteration, RecursionError):
        corrupt()


def _validate(value):
    if not isinstance(value, dict) or type(value.get('schema_version')) is not int or value['schema_version'] != 2:
        raise CharacterSessionError('SCHEMA_READ_ONLY')
    canonical_id(value.get('session_id'))
    if value.get('deleted') is True:
        fields(value, {'schema_version', 'session_id', 'deleted'})
        return
    fields(value, {'schema_version', 'session_id', 'creation_fingerprint', 'participants', 'world_binding',
                   'created_at', 'title', 'presentation_mode', 'revision', 'updated_at', 'extensions',
                   'context_epoch', 'next_seq', 'read_ai_seq', 'inputs', 'groups', 'requests', 'ledger'}, {'opening'})
    validate_envelope(value)
    from .proactive_contact import validate_stored
    validate_stored(value)
    validate_depth(value, 40)
    if len(json_bytes(value)) > MAX_FILE_BYTES:
        raise CharacterSessionError('SESSION_LIMIT')
    integer(value['context_epoch']); integer(value['next_seq'], 1); integer(value['read_ai_seq'])
    for key, limit in (('inputs', MAX_ACTIONS), ('groups', MAX_ATTEMPTS), ('requests', MAX_ACTIONS), ('ledger', MAX_LEDGER)):
        if not isinstance(value[key], list):
            corrupt()
        if len(value[key]) > limit:
            raise CharacterSessionError('SESSION_LIMIT')
    if len(capacity_groups(value)) > MAX_TURNS:
        raise CharacterSessionError('SESSION_LIMIT')
    ids = {p['controller']: p['instance_id'] for p in value['participants']}
    audience = set(ids.values())
    messages, sequences, inputs, groups, actions, attempts = {}, set(), {}, {}, {}, {}
    all_identity = set(audience)

    def identity(identifier):
        canonical_id(identifier)
        if identifier in all_identity:
            corrupt()
        all_identity.add(identifier)

    def message(m, controller, delivered):
        fields(m, {'message_id', 'speaker_instance_id', 'content', 'presentation_mode', 'visibility'},
               {'seq', 'created_at', 'turn_id'})
        identity(m['message_id'])
        if m['speaker_instance_id'] != ids[controller] or m['presentation_mode'] not in {'messenger', 'roleplay'}:
            corrupt()
        fields(m['visibility'], {'audience_instance_ids'})
        if not isinstance(m['visibility']['audience_instance_ids'], list) or len(m['visibility']['audience_instance_ids']) != 2 or set(m['visibility']['audience_instance_ids']) != audience:
            corrupt()
        text(m['content'], 4000 if controller == 'user' else 8000)
        if delivered:
            seq = integer(m['seq'], 1, value['next_seq'] - 1)
            text(m['created_at'], 64)
            if 'turn_id' not in m:
                timestamp(m['created_at'])
            if seq in sequences:
                corrupt()
            sequences.add(seq)
        elif 'seq' in m or 'created_at' in m:
            corrupt()
        if 'turn_id' in m:
            canonical_id(m['turn_id'])
        messages[m['message_id']] = m

    for entry in value['inputs']:
        fields(entry, {'input_id', 'action_id', 'message', 'status'}, {'ooc_note'})
        if entry['input_id'] != entry['message']['message_id'] or entry['status'] not in {'active', 'withdrawn'}:
            corrupt()
        message(entry['message'], 'user', True)
        canonical_id(entry['action_id'])
        validate_stored_ooc(entry)
        inputs[entry['input_id']] = entry
    busy = 0
    inverse_entries, plans = [], []
    for group in value['groups']:
        fields(group, {'group_id', 'action_id', 'request_id', 'input_ids', 'mode_at_generation', 'display_mode',
                       'status', 'created_at', 'bubbles', 'delivered_count', 'next_due_at', 'ledger_plan', 'ledger_inverse'},
               {'generated_at', 'settled_at', 'committed_revision', 'replaced_by_group_id', 'error_code', 'memory_notice',
                'origin', 'contact_ref'})
        identity(group['group_id'])
        canonical_id(group['action_id']); canonical_id(group['request_id'])
        if group['status'] not in CURRENT_GROUP_STATES | {'replaced', 'withdrawn'}:
            corrupt()
        if group['mode_at_generation'] not in {'messenger', 'roleplay'} or group['display_mode'] not in {'stream', 'gaps', 'instant'}:
            corrupt()
        members = group['input_ids']
        proactive = group.get('origin') == 'proactive'
        if group.get('origin', 'reply') not in {'reply', 'proactive'}:
            corrupt()
        if proactive:
            fields(group.get('contact_ref'), {'plan_id', 'index'})
            canonical_id(group['contact_ref']['plan_id'])
            integer(group['contact_ref']['index'], 0, 4)
            if (members or group['display_mode'] != 'instant' or group.get('memory_notice')
                    or group['status'] not in {'complete', 'withdrawn'}):
                corrupt()
        elif 'contact_ref' in group:
            corrupt()
        if not isinstance(members, list) or not (0 if proactive else 1) <= len(members) <= 8 or len(set(members)) != len(members) or any(mid not in inputs for mid in members):
            corrupt()
        if group['status'] in {'generating', 'delivering', 'complete', 'partial_failed'} and any(inputs[mid]['status'] != 'active' for mid in members):
            corrupt()
        if not isinstance(group['bubbles'], list) or len(group['bubbles']) > 6:
            corrupt()
        count = integer(group['delivered_count'], 0, len(group['bubbles']))
        if group['status'] in {'complete', 'replaced', 'withdrawn'} and (not group['bubbles'] or count != len(group['bubbles'])):
            corrupt()
        if group['status'] == 'generating' and (group['bubbles'] or count):
            corrupt()
        if group['status'] == 'delivering':
            if group['display_mode'] != 'gaps' or not 0 < count < len(group['bubbles']):
                corrupt()
            timestamp(group['next_due_at'])
        elif group['next_due_at'] is not None:
            corrupt()
        busy += group['status'] in {'generating', 'delivering'}
        total = 0
        for ordinal, bubble in enumerate(group['bubbles']):
            fields(bubble, {'ordinal', 'message'})
            if type(bubble['ordinal']) is not int or bubble['ordinal'] != ordinal:
                corrupt()
            message(bubble['message'], 'ai', ordinal < count)
            total += len(bubble['message']['content'])
        if total > 8000:
            corrupt()
        inverse = group['ledger_inverse']
        fields(inverse, {'added_entry_ids', 'previous_entries'})
        if not isinstance(inverse['added_entry_ids'], list) or not isinstance(inverse['previous_entries'], list) or len(inverse['added_entry_ids']) > 6 or len(inverse['previous_entries']) > 6:
            corrupt()
        if len(set(inverse['added_entry_ids'])) != len(inverse['added_entry_ids']):
            corrupt()
        for eid in inverse['added_entry_ids']:
            canonical_id(eid)
        inverse_entries.extend(inverse['previous_entries'])
        validate_notice(group)
        if not isinstance(group['ledger_plan'], list) or len(group['ledger_plan']) > 6 or (group['status'] != 'delivering' and group['ledger_plan']):
            corrupt()
        for item in group['ledger_plan']:
            fields(item, {'entry'}, {'previous_entry'})
            if item['entry']['created_turn_id'] != group['group_id'] or item['entry']['status'] != 'active':
                corrupt()
            previous = item.get('previous_entry')
            if previous:
                target = next((e for e in value['ledger'] if e['entry_id'] == previous['entry_id']), None)
                if (target != previous or previous['status'] != 'active'
                        or item['entry'].get('supersedes_entry_id') != previous['entry_id']
                        or any(item['entry'].get(k) != previous.get(k) for k in ('kind', 'about_instance_id', 'subject_instance_id'))
                        or not set(item['entry']['visibility']['audience_instance_ids']) <= set(previous['visibility']['audience_instance_ids'])):
                    corrupt()
            elif item['entry'].get('supersedes_entry_id'):
                corrupt()
            plans.append(item['entry'])
        groups[group['group_id']] = group
    if busy > 1:
        corrupt()
    pending, reservations, materialized_reservations = 0, set(), set()
    legacy_reservations, legacy_executions, legacy_signatures = {}, [], {}
    def legacy_snapshot(snapshot, action, attempt):
        fields(snapshot, {'content', 'mode', 'user_message_id', 'ai_message_id'},
               {'ooc_note', 'reply_contract_id', 'context_contract_id'})
        text(snapshot['content'], 4000)
        canonical_id(snapshot['user_message_id']); canonical_id(snapshot['ai_message_id'])
        if snapshot['user_message_id'] == snapshot['ai_message_id']:
            corrupt()
        if snapshot['mode'] not in {'messenger', 'roleplay'}:
            corrupt()
        validate_stored_ooc(snapshot)
        contract = validate_contract(attempt.get('reply_contract_id', V1))
        context = validate_context_contract(attempt.get('context_contract_id', LEGACY))
        if contract not in {V1, V2} or snapshot.get('reply_contract_id', contract) != contract:
            corrupt()
        if context == C4 or snapshot.get('context_contract_id', context) != context or bool(snapshot.get('ooc_note')) != (context == C3):
            corrupt()
        signature = (snapshot['content'], snapshot['mode'], snapshot['user_message_id'], snapshot['ai_message_id'],
                     snapshot.get('ooc_note', ''), contract, context)
        if legacy_signatures.setdefault(action['action_id'], signature) != signature:
            corrupt()
        for key in ('user_message_id', 'ai_message_id'):
            mid = snapshot[key]
            owner = legacy_reservations.setdefault(mid, (action['action_id'], key))
            if owner != (action['action_id'], key):
                corrupt()
    for action in value['requests']:
        fields(action, {'action_id', 'operation', 'fingerprint', 'created_at', 'mode_at_action', 'result_state', 'attempts'},
               {'input_id', 'target_group_id', 'result_group_id', 'resolved_by_group_id', 'legacy_retry_snapshot'})
        identity(action['action_id'])
        actions[action['action_id']] = action
        if action['operation'] not in {'send', 'regenerate', 'undo', 'proactive'} or action['result_state'] not in {None, 'active', 'withdrawn', 'replaced'}:
            corrupt()
        if action['operation'] == 'proactive' and ('input_id' in action or len(action['attempts']) != 1):
            corrupt()
        text(action['fingerprint'], 64)
        if not isinstance(action['attempts'], list):
            corrupt()
        if 'legacy_retry_snapshot' in action:
            if not action['attempts'] or not all(a.get('legacy_attempt') is True for a in action['attempts']):
                corrupt()
            legacy_snapshot(action['legacy_retry_snapshot'], action, action['attempts'][-1])
            if action.get('result_group_id') or action['result_state'] is not None:
                corrupt()
        if 'input_id' in action and (action['input_id'] not in inputs or inputs[action['input_id']]['action_id'] != action['action_id']):
            corrupt()
        for key in ('target_group_id', 'result_group_id', 'resolved_by_group_id'):
            if key in action and action[key] not in groups:
                corrupt()
        for attempt in action['attempts']:
            # Old attempts are explicitly bounded compatibility records, never
            # reinterpreted as v3 current inputs or candidates.
            if attempt.get('control_attempt') is True:
                fields(attempt, {'request_id', 'base_revision', 'status', 'created_at', 'ended_at', 'committed_revision', 'control_attempt'})
                if action['operation'] != 'undo' or attempt['status'] != 'committed':
                    corrupt()
            elif attempt.get('legacy_attempt') is True:
                fields(attempt, {'request_id', 'base_revision', 'status', 'legacy_attempt'},
                       {'created_at', 'ended_at', 'error_code', 'committed_revision', 'retry_of', 'retry_token',
                        'reply_contract_id', 'context_contract_id', 'legacy_retry_snapshot', 'legacy_execution'})
                if validate_contract(attempt.get('reply_contract_id', V1)) not in {V1, V2}:
                    corrupt()
                if validate_context_contract(attempt.get('context_contract_id', LEGACY)) == C4:
                    corrupt()
                if 'legacy_retry_snapshot' in attempt:
                    legacy_snapshot(attempt['legacy_retry_snapshot'], action, attempt)
                if 'legacy_execution' in attempt:
                    execution = attempt['legacy_execution']
                    fields(execution, {'group_id', 'context_epoch', 'history_cutoff_seq', 'display_mode'})
                    canonical_id(execution['group_id'])
                    integer(execution['context_epoch'], 0, value['context_epoch'])
                    integer(execution['history_cutoff_seq'], 0, value['next_seq'] - 1)
                    if execution['display_mode'] not in {'stream', 'gaps', 'instant'} or not attempt.get('legacy_retry_snapshot'):
                        corrupt()
                    legacy_executions.append((action, attempt, execution))
            else:
                fields(attempt, {'request_id', 'base_revision', 'context_epoch', 'history_cutoff_seq', 'input_ids',
                                 'group_id', 'reserved_ai_ids', 'reply_contract_id', 'context_contract_id',
                                 'display_mode', 'status', 'created_at'},
                       {'ended_at', 'error_code', 'committed_revision', 'retry_of', 'retry_token'})
                if attempt['reply_contract_id'] != V3 or attempt['group_id'] not in groups:
                    corrupt()
                if attempt['context_contract_id'] != C4:
                    corrupt()
                integer(attempt['context_epoch']); integer(attempt['history_cutoff_seq'], 0, value['next_seq'] - 1)
                group = groups[attempt['group_id']]
                if attempt['input_ids'] != group['input_ids'] or attempt['display_mode'] != group['display_mode']:
                    corrupt()
                reserved = attempt['reserved_ai_ids']
                if not isinstance(reserved, list) or len(reserved) != 6 or len(set(reserved)) != 6:
                    corrupt()
                for rid in reserved:
                    canonical_id(rid)
                    if rid in reservations:
                        corrupt()
                    reservations.add(rid)
                if [b['message']['message_id'] for b in group['bubbles']] != reserved[:len(group['bubbles'])]:
                    corrupt()
                materialized_reservations.update(b['message']['message_id'] for b in group['bubbles'])
            identity(attempt['request_id'])
            attempts[attempt['request_id']] = (action, attempt)
            integer(attempt['base_revision'])
            if attempt['status'] not in {'pending', 'committed', 'failed', 'cancelled', 'interrupted'}:
                corrupt()
            pending += attempt['status'] == 'pending'
    if pending > 1 or len(attempts) > MAX_ATTEMPTS:
        corrupt()
    if (reservations & all_identity) != materialized_reservations:
        corrupt()
    for action, attempt, execution in legacy_executions:
        group = groups.get(execution['group_id'])
        if attempt['status'] == 'committed':
            snapshot = attempt['legacy_retry_snapshot']
            if (not group or group['request_id'] != attempt['request_id'] or group['action_id'] != action['action_id']
                    or group['input_ids'] != [snapshot['user_message_id']] or len(group['bubbles']) != 1
                    or group['bubbles'][0]['message']['message_id'] != snapshot['ai_message_id']
                    or group['display_mode'] != execution['display_mode'] or group['mode_at_generation'] != snapshot['mode']):
                corrupt()
            source_input = inputs.get(snapshot['user_message_id'])
            if (not source_input or source_input['message']['content'] != snapshot['content']
                    or source_input['message']['presentation_mode'] != snapshot['mode']
                    or source_input.get('ooc_note', '') != snapshot.get('ooc_note', '')):
                corrupt()
        else:
            if group is not None:
                corrupt()
            identity(execution['group_id'])
        if attempt['status'] == 'pending':
            busy += 1
            if (action['attempts'][-1] is not attempt or execution['context_epoch'] != value['context_epoch']
                    or execution['history_cutoff_seq'] != value['next_seq'] - 1
                    or action.get('legacy_retry_snapshot') != attempt['legacy_retry_snapshot']
                    or action.get('result_group_id') or action['result_state'] is not None or pending_inputs(value)):
                corrupt()
    if busy > 1:
        corrupt()
    for mid, (aid, key) in legacy_reservations.items():
        if mid in reservations:
            corrupt()
        if mid in all_identity:
            message_value = messages.get(mid)
            owned_groups = [g for g in value['groups'] if g['action_id'] == aid]
            materialized = (any(mid in g['input_ids'] for g in owned_groups) if key == 'user_message_id'
                            else any(b['message']['message_id'] == mid for g in owned_groups for b in g['bubbles']))
            if message_value is None or not materialized:
                corrupt()
        else:
            reservations.add(mid)
    for entry in value['inputs']:
        owner = actions.get(entry['action_id'])
        legacy_regeneration = (owner and owner['operation'] == 'regenerate' and owner['attempts']
                               and all(a.get('legacy_attempt') is True for a in owner['attempts'])
                               and any(g['action_id'] == owner['action_id'] and entry['input_id'] in g['input_ids'] for g in value['groups']))
        if (not owner or owner['operation'] != 'send' and not legacy_regeneration
                or owner.get('input_id') != entry['input_id']):
            corrupt()
    for group in value['groups']:
        owner = attempts.get(group['request_id'])
        if owner is None or owner[0]['action_id'] != group['action_id']:
            corrupt()
        if (group.get('origin') == 'proactive') != (owner[0]['operation'] == 'proactive'):
            corrupt()
        if owner[1].get('legacy_execution') and owner[1]['legacy_execution']['group_id'] != group['group_id']:
            corrupt()
        if not owner[1].get('legacy_attempt') and owner[1]['group_id'] != group['group_id']:
            corrupt()
        if not owner[1].get('legacy_attempt'):
            timestamp(group['created_at'])
            timestamp(owner[1]['created_at'])
            if group['status'] in {'delivering', 'complete', 'replaced', 'withdrawn'}:
                timestamp(group['generated_at'])
            if group['status'] in {'complete', 'replaced', 'withdrawn', 'failed', 'cancelled', 'interrupted', 'partial_failed'}:
                timestamp(group['settled_at'])
            if group['status'] in {'complete', 'replaced', 'withdrawn', 'partial_failed'}:
                integer(group['committed_revision'], 1, value['revision'])
        if group['status'] == 'generating' and owner[1]['status'] != 'pending':
            corrupt()
        if group['status'] in {'delivering', 'complete', 'replaced', 'withdrawn'} and owner[1]['status'] != 'committed':
            corrupt()
        if group['status'] in {'failed', 'cancelled', 'interrupted'} and owner[1]['status'] != group['status']:
            corrupt()
    maximum_ai = max((m['seq'] for m in messages.values() if 'seq' in m and m['speaker_instance_id'] == ids['ai']), default=0)
    if value['read_ai_seq'] > maximum_ai:
        corrupt()
    entry_ids = set()
    active = 0
    planned_start = len(value['ledger']) + len(inverse_entries)
    plan_ids, superseded_plan_ids = set(), set()
    current_source_ids = set(current_messages(value))
    for index, entry in enumerate([*value['ledger'], *inverse_entries, *plans]):
        fields(entry, {'entry_id', 'subject_instance_id', 'kind', 'content', 'source', 'visibility', 'status', 'created_turn_id'},
               {'about_instance_id', 'supersedes_entry_id', 'memory_annotation'})
        canonical_id(entry['entry_id'])
        if index < len(value['ledger']):
            if entry['entry_id'] in entry_ids | all_identity | reservations:
                corrupt()
            entry_ids.add(entry['entry_id'])
            active += entry['status'] == 'active'
        elif index >= planned_start:
            if entry['entry_id'] in entry_ids | plan_ids | all_identity:
                corrupt()
            plan_ids.add(entry['entry_id'])
            target_id = entry.get('supersedes_entry_id')
            if target_id:
                if target_id in superseded_plan_ids:
                    corrupt()
                superseded_plan_ids.add(target_id)
        text(entry['content'], 400)
        if entry['subject_instance_id'] != ids['ai'] or entry['status'] not in {'active', 'superseded'} or entry['kind'] not in {'knowledge', 'belief', 'experience', 'intent', 'relationship'}:
            corrupt()
        origin = groups.get(entry['created_turn_id'])
        if origin is None:
            corrupt()
        origin_attempt = attempts[origin['request_id']][1]
        legacy_origin = origin_attempt.get('legacy_attempt') is True
        visible = entry['visibility']['audience_instance_ids']
        if not isinstance(visible, list) or len(set(visible)) != len(visible) or set(visible) not in ({ids['ai']}, audience):
            corrupt()
        about = entry.get('about_instance_id')
        if about is not None and about not in audience or entry['kind'] == 'relationship' and about != ids['user']:
            corrupt()
        source = entry['source']
        fields(source, {'type', 'message_ids', 'evidence'})
        if source['type'] not in {'author', 'player_statement', 'dialogue_event', 'model_inference'}:
            corrupt()
        refs, evidence = source['message_ids'], source['evidence']
        if not isinstance(refs, list) or not (0 if source['type'] == 'author' else 1) <= len(refs) <= 2 or len(set(refs)) != len(refs) or not isinstance(evidence, list) or len(evidence) > 2:
            corrupt()
        if not legacy_origin:
            count = len(origin['bubbles']) if index >= planned_start else origin['delivered_count']
            current_ids = set(origin['input_ids']) | {b['message']['message_id'] for b in origin['bubbles'][:count]}
            if (source['type'] == 'author' or not evidence
                    or entry['kind'] == 'experience' and source['type'] != 'dialogue_event'
                    or source['type'] == 'dialogue_event' and not set(refs) <= current_ids):
                corrupt()
        if source['type'] == 'model_inference' and entry['kind'] not in {'belief', 'intent', 'relationship'}:
            corrupt()
        for mid in refs:
            candidate_allowed = (index >= planned_start and mid in {b['message']['message_id'] for b in origin['bubbles']})
            if mid not in messages or ('seq' not in messages[mid] and not candidate_allowed) or not set(visible) <= set(messages[mid]['visibility']['audience_instance_ids']):
                corrupt()
            current_origin = origin['status'] in {'generating', 'delivering', 'complete', 'partial_failed'}
            if not legacy_origin and current_origin and mid not in current_source_ids and not candidate_allowed:
                corrupt()
            if source['type'] == 'player_statement' and messages[mid]['speaker_instance_id'] != ids['user']:
                corrupt()
        for quote in evidence:
            fields(quote, {'message_id', 'quote'})
            text(quote['quote'], 240)
            if quote['message_id'] not in refs or quote['quote'] not in messages[quote['message_id']]['content']:
                corrupt()
        if 'memory_annotation' in entry:
            validate_annotation(entry['memory_annotation'], entry, ids['user'])
            if not refs or not evidence or attempts[origin['request_id']][1].get('reply_contract_id', V1) not in {V2, V3}:
                corrupt()
            count = len(origin['bubbles']) if index >= planned_start else origin['delivered_count']
            current_ids = set(origin['input_ids']) | {b['message']['message_id'] for b in origin['bubbles'][:count]}
            if source['type'] == 'dialogue_event' and not set(refs) <= current_ids:
                corrupt()
    if active > MAX_ACTIVE:
        raise CharacterSessionError('SESSION_LIMIT')
    if len(value['ledger']) + len(plans) > MAX_LEDGER or active + len(plans) - len(superseded_plan_ids) > MAX_ACTIVE:
        raise CharacterSessionError('SESSION_LIMIT')
    by_entry_id = {e['entry_id']: e for e in value['ledger']}
    for group in value['groups']:
        if group['status'] == 'complete' and group.get('memory_notice'):
            if actions[group['action_id']]['operation'] != 'send':
                corrupt()
            for eid in group['memory_notice']['entry_ids']:
                entry = by_entry_id.get(eid)
                if (not entry or not entry.get('memory_annotation') or entry['created_turn_id'] != group['group_id']
                        or set(entry['visibility']['audience_instance_ids']) != audience or entry.get('supersedes_entry_id')):
                    corrupt()
    validate_opening(value.get('opening'), ids['ai'], value['created_at'], all_identity | entry_ids | reservations | plan_ids)
