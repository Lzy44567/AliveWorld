"""Bounded, source-aware recall policy; no model calls or global player profile."""
import re
import unicodedata
from uuid import UUID


LIMIT = 8


class MemoryVersionError(ValueError):
    pass


def settings(session):
    value = session.get('extensions', {}).get('character_memory', {'version': 1, 'important_entry_ids': []})
    if isinstance(value, dict) and type(value.get('version')) is int and value['version'] != 1:
        raise MemoryVersionError('Unsupported memory version')
    if not isinstance(value, dict) or set(value) != {'version', 'important_entry_ids'} or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Invalid memory settings')
    ids = value['important_entry_ids']
    if not isinstance(ids, list) or len(ids) > LIMIT or any(not isinstance(i, str) or str(UUID(i)) != i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Invalid memory roots')
    return {'version': 1, 'important_entry_ids': list(ids)}


def normalize(value):
    return unicodedata.normalize('NFKC', value).casefold()


def units(value, limit=128):
    result = []
    for match in re.finditer(r'[\u3400-\u9fff]+|[a-z0-9]+', normalize(value)):
        token = match.group()
        pieces = [token[i:i + 2] for i in range(len(token) - 1)] if re.fullmatch(r'[\u3400-\u9fff]+', token) else [token]
        for piece in pieces:
            if piece not in result:
                result.append(piece)
                if limit is not None and len(result) == limit:
                    return result
    return result


def formal_messages(session):
    return {m['message_id']: m for t in session['turns'] for m in (t['user_message'], t['ai_message'])}


def valid_candidates(session):
    ai = next(p['instance_id'] for p in session['participants'] if p['controller'] == 'ai')
    turns = {t['turn_id'] for t in session['turns']}
    messages = formal_messages(session)
    return [e for e in session['ledger'] if e['status'] == 'active' and ai in e['visibility']['audience_instance_ids']
            and e['subject_instance_id'] == ai and e['created_turn_id'] in turns
            and all(mid in messages for mid in e['source']['message_ids'])]


def public(entry, session):
    return set(entry['visibility']['audience_instance_ids']) == {p['instance_id'] for p in session['participants']}


def root_for(entry, session):
    roots = set(settings(session)['important_entry_ids'])
    by_id = {e['entry_id']: e for e in session['ledger']}
    seen, found = set(), None
    current = entry
    for _ in range(2048):
        eid = current['entry_id']
        if eid in seen:
            return None
        seen.add(eid)
        if eid in roots:
            found = eid
        previous_id = current.get('supersedes_entry_id')
        if previous_id is None:
            return found
        previous = by_id.get(previous_id)
        if previous is None or previous.get('status') != 'superseded' or any(previous.get(k) != entry.get(k) for k in ('subject_instance_id', 'kind', 'about_instance_id')):
            return None
        if not set(current['visibility']['audience_instance_ids']) <= set(previous['visibility']['audience_instance_ids']):
            return None
        current = previous
    return None


def public_state(session):
    visible = [e for e in valid_candidates(session) if public(e, session)]
    protected = {e['entry_id']: root_for(e, session) for e in visible}
    effective = {root for root in protected.values() if root}
    return {'version': 1, 'important_entry_ids': settings(session)['important_entry_ids'],
            'protected_entries': [{'entry_id': eid, 'root_entry_id': root} for eid, root in protected.items() if root],
            'inactive_root_ids': [root for root in settings(session)['important_entry_ids'] if root not in effective]}


def select_memory(session, current_input):
    query = set(units(current_input))
    order = {t['turn_id']: i for i, t in enumerate(session['turns'])}
    candidates = valid_candidates(session)
    scores = {e['entry_id']: len(query.intersection(units(e['content'], limit=None))) for e in candidates}
    roots = {e['entry_id']: root_for(e, session) for e in candidates}
    candidates.sort(key=lambda e: (not bool(roots[e['entry_id']]), -scores[e['entry_id']], -order[e['created_turn_id']], e['entry_id']))
    selected, intents = [], 0
    for entry in candidates:
        if entry['kind'] == 'intent':
            if intents == 8:
                continue
            intents += 1
        if len(selected) < 32:
            selected.append(entry)
    return selected, [{'entry_id': e['entry_id'], 'reason': 'important' if roots[e['entry_id']] else 'related' if scores[e['entry_id']] else 'recent'}
                      for e in candidates if public(e, session)]


def final_report(candidates, selected_ids, final_ids):
    return {'entries': [dict(e, state='sent' if e['entry_id'] in final_ids else 'budget' if e['entry_id'] in selected_ids else 'not_selected') for e in candidates]}
