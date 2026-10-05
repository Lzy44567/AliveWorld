"""Strict one-turn output validation and reversible, source-aware local ledger."""
import copy
import json
from datetime import datetime, timezone
from uuid import uuid4

from .models import CharacterSessionError, json_bytes, text, validate_depth
from .protocol import V1, V2, result_keys
from .annotations import parse_annotations, validate_annotation
from .memory import select_memory, public


def now():
    return datetime.now(timezone.utc).isoformat()


def unique_object(pairs):
    value = {}
    for key, child in pairs:
        if key in value:
            raise CharacterSessionError("CONTRACT_INVALID")
        value[key] = child
    return value


def parse_result(raw, contract_id=V1):
    try:
        if not isinstance(raw, str) or len(raw.encode('utf-8')) > 65536:
            raise CharacterSessionError('CONTRACT_INVALID')
        value = json.loads(raw, object_pairs_hook=unique_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(CharacterSessionError('CONTRACT_INVALID')))
        validate_depth(value, 12)
        json_bytes(value)  # Reject isolated surrogate code points even without streaming.
        if not isinstance(value, dict) or set(value) != result_keys(contract_id):
            raise CharacterSessionError('CONTRACT_INVALID')
        text(value['reply'], 8000)
        if not isinstance(value['ledger_ops'], list) or len(value['ledger_ops']) > 6:
            raise CharacterSessionError('CONTRACT_INVALID')
        if contract_id == V2:
            parse_annotations(value['memory_annotations'], value['ledger_ops'])
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise CharacterSessionError('CONTRACT_INVALID') from None


def public_ledger(session, spoiler=False):
    ids = {p['instance_id'] for p in session['participants']}
    allowed = {'entry_id', 'subject_instance_id', 'kind', 'content', 'source', 'visibility',
               'status', 'created_turn_id', 'about_instance_id', 'supersedes_entry_id', 'memory_annotation'}
    return [{k: copy.deepcopy(v) for k, v in e.items() if k in allowed} for e in session['ledger'] if e['status'] == 'active'
            and (spoiler or set(e['visibility']['audience_instance_ids']) == ids)]


def reverse_ledger(session, inverse):
    added = set(inverse['added_entry_ids'])
    session['ledger'] = [e for e in session['ledger'] if e['entry_id'] not in added]
    previous = {e['entry_id']: e for e in inverse['previous_entries']}
    session['ledger'] = [copy.deepcopy(previous.get(e['entry_id'], e)) for e in session['ledger']]


def plan_turn(session, action, attempt, raw, allowed_messages, projected_entry_ids, contract_id=V1):
    try:
        return _plan_turn(session, action, attempt, raw, allowed_messages, projected_entry_ids, contract_id)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise CharacterSessionError('CONTRACT_INVALID') from None


def _plan_turn(session, action, attempt, raw, allowed_messages, projected_entry_ids, contract_id):
    result = parse_result(raw, contract_id)
    annotations = parse_annotations(result['memory_annotations'], result['ledger_ops']) if contract_id == V2 else {}
    candidate = copy.deepcopy(session)
    pending = attempt['pending_input']
    participants = {p['controller']: p['instance_id'] for p in session['participants']}
    audience = list(participants.values())
    turn_id, timestamp = str(uuid4()), now()
    def message(message_id, speaker, content):
        return {'message_id': message_id, 'turn_id': turn_id,
                'speaker_instance_id': participants[speaker], 'content': content,
                'presentation_mode': pending['mode'],
                'visibility': {'audience_instance_ids': audience}, 'created_at': timestamp}
    user = message(pending['user_message_id'], 'user', pending['content'])
    reply = message(pending['ai_message_id'], 'ai', result['reply'])
    messages = {m['message_id']: m for m in [*allowed_messages, user, reply]}
    inverse = {'added_entry_ids': [], 'previous_entries': []}
    touched = set()
    for op_index, op in enumerate(result['ledger_ops']):
        if not isinstance(op, dict):
            raise CharacterSessionError('CONTRACT_INVALID')
        required = {'op', 'kind', 'content', 'source', 'visibility'}
        allowed = required | {'about_instance_id'}
        if op.get('op') == 'supersede':
            required.add('target_entry_id')
            allowed.add('target_entry_id')
        if not required <= set(op) or not set(op) <= allowed or op['op'] not in {'add', 'supersede'}:
            raise CharacterSessionError('CONTRACT_INVALID')
        kind = op['kind']
        if kind not in {'knowledge', 'belief', 'experience', 'intent', 'relationship'}:
            raise CharacterSessionError('CONTRACT_INVALID')
        text(op['content'], 400)
        about = op.get('about_instance_id')
        if about is not None and about not in audience:
            raise CharacterSessionError('CONTRACT_INVALID')
        if kind == 'relationship' and about != participants['user']:
            raise CharacterSessionError('CONTRACT_INVALID')
        visibility = op['visibility']
        if not isinstance(visibility, dict) or set(visibility) != {'audience_instance_ids'}:
            raise CharacterSessionError('CONTRACT_INVALID')
        visible = visibility['audience_instance_ids']
        if not isinstance(visible, list) or len(visible) != len(set(visible)) or set(visible) not in ({participants['ai']}, set(audience)):
            raise CharacterSessionError('CONTRACT_INVALID')
        source = op['source']
        if not isinstance(source, dict) or set(source) != {'type', 'message_ids', 'evidence'}:
            raise CharacterSessionError('CONTRACT_INVALID')
        source_type = source['type']
        if source_type not in {'player_statement', 'dialogue_event', 'model_inference'}:
            raise CharacterSessionError('CONTRACT_INVALID')
        if source_type == 'model_inference' and kind not in {'belief', 'intent', 'relationship'}:
            raise CharacterSessionError('CONTRACT_INVALID')
        if kind == 'experience' and source_type != 'dialogue_event':
            raise CharacterSessionError('CONTRACT_INVALID')
        refs = source['message_ids']
        evidence = source['evidence']
        if not isinstance(refs, list) or not 1 <= len(refs) <= 2 or len(refs) != len(set(refs)):
            raise CharacterSessionError('CONTRACT_INVALID')
        if not isinstance(evidence, list) or not 1 <= len(evidence) <= 2:
            raise CharacterSessionError('CONTRACT_INVALID')
        for ref in refs:
            if ref not in messages or not set(visible) <= set(messages[ref]['visibility']['audience_instance_ids']):
                raise CharacterSessionError('CONTRACT_INVALID')
            if source_type == 'player_statement' and messages[ref]['speaker_instance_id'] != participants['user']:
                raise CharacterSessionError('CONTRACT_INVALID')
        for item in evidence:
            if not isinstance(item, dict) or set(item) != {'message_id', 'quote'} or item['message_id'] not in refs:
                raise CharacterSessionError('CONTRACT_INVALID')
            text(item['quote'], 240)
            if item['quote'] not in messages[item['message_id']]['content']:
                raise CharacterSessionError('CONTRACT_INVALID')
        if source_type == 'dialogue_event' and not set(refs) <= {user['message_id'], reply['message_id']}:
            raise CharacterSessionError('CONTRACT_INVALID')
        entry = {'entry_id': str(uuid4()), 'subject_instance_id': participants['ai'],
                 'kind': kind, 'content': op['content'], 'source': copy.deepcopy(source),
                 'visibility': copy.deepcopy(visibility), 'status': 'active', 'created_turn_id': turn_id}
        if about is not None:
            entry['about_instance_id'] = about
        if op_index in annotations:
            entry['memory_annotation'] = validate_annotation(annotations[op_index], entry, participants['user'])
        if op['op'] == 'supersede':
            target = op['target_entry_id']
            old = next((e for e in candidate['ledger'] if e['entry_id'] == target), None)
            if target in touched or target not in projected_entry_ids or old is None or old['status'] != 'active':
                raise CharacterSessionError('CONTRACT_INVALID')
            if old['kind'] != kind or old.get('about_instance_id') != about or old['subject_instance_id'] != participants['ai']:
                raise CharacterSessionError('CONTRACT_INVALID')
            if not set(visible) <= set(old['visibility']['audience_instance_ids']):
                raise CharacterSessionError('CONTRACT_INVALID')
            touched.add(target)
            inverse['previous_entries'].append(copy.deepcopy(old))
            old['status'] = 'superseded'
            entry['supersedes_entry_id'] = target
        candidate['ledger'].append(entry)
        inverse['added_entry_ids'].append(entry['entry_id'])
    if len(candidate['ledger']) > 2048 or sum(e['status'] == 'active' for e in candidate['ledger']) > 128:
        raise CharacterSessionError('SESSION_LIMIT')
    turn = {'turn_id': turn_id, 'action_id': action['action_id'], 'request_id': attempt['request_id'],
            'user_message': user, 'ai_message': reply, 'mode_at_generation': pending['mode'],
            'ledger_inverse': inverse, 'committed_revision': session['revision'] + 1, 'created_at': timestamp}
    candidate['turns'].append(turn)
    if annotations and action['operation'] == 'send':
        _, report = select_memory(candidate, pending['content'])
        selected = {e['entry_id'] for e in report if e['reason'] in {'auto_important', 'auto_highlight'}}
        ids = [e['entry_id'] for e in candidate['ledger'] if e['entry_id'] in inverse['added_entry_ids']
               and e['entry_id'] in selected and not e.get('supersedes_entry_id') and public(e, candidate)]
        if ids:
            turn['memory_notice'] = {'action_id': action['action_id'], 'committed_revision': turn['committed_revision'], 'entry_ids': ids}
    return candidate, turn
