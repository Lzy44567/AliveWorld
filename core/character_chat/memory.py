"""Bounded, source-aware recall policy; no model calls or global player profile."""
import re
import unicodedata
from uuid import UUID
from .annotations import automatic_grades, chain_root, GRADES


LIMIT = 8


class MemoryVersionError(ValueError):
    pass


def settings(session):
    value = session.get('extensions', {}).get('character_memory', {'version': 1, 'important_entry_ids': []})
    if isinstance(value, dict) and type(value.get('version')) is int and value['version'] not in {1, 2}:
        raise MemoryVersionError('Unsupported memory version')
    if not isinstance(value, dict) or type(value.get('version')) is not int or value['version'] not in {1, 2}:
        raise ValueError('Invalid memory settings')
    keys = {'version', 'important_entry_ids'}
    if value['version'] == 2:
        keys |= {'dismissed_auto_root_ids', 'notice_ack_revision'}
    if set(value) != keys:
        raise ValueError('Invalid memory settings')
    ids = value['important_entry_ids']
    if not isinstance(ids, list) or len(ids) > LIMIT or any(not isinstance(i, str) or str(UUID(i)) != i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Invalid memory roots')
    result = {'version': value['version'], 'important_entry_ids': list(ids)}
    if value['version'] == 2:
        dismissed, ack = value['dismissed_auto_root_ids'], value['notice_ack_revision']
        if not isinstance(dismissed, list) or len(dismissed) > 128 or any(not isinstance(i, str) or str(UUID(i)) != i for i in dismissed) or len(set(dismissed)) != len(dismissed):
            raise ValueError('Invalid dismissed roots')
        if type(ack) is not int or not 0 <= ack <= session['revision']:
            raise ValueError('Invalid notice acknowledgement')
        result.update(dismissed_auto_root_ids=list(dismissed), notice_ack_revision=ack)
    return result


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
    config = settings(session)
    result = {'version': config['version'], 'important_entry_ids': config['important_entry_ids'],
            'protected_entries': [{'entry_id': eid, 'root_entry_id': root} for eid, root in protected.items() if root],
            'inactive_root_ids': [root for root in config['important_entry_ids'] if root not in effective]}
    if config['version'] == 2:
        active_roots = {chain_root(e, session) for e in valid_candidates(session)}
        result.update(automatic_enabled=True, notice_ack_revision=config['notice_ack_revision'],
                      inactive_dismissed_root_ids=[root for root in config['dismissed_auto_root_ids'] if root not in active_roots and None not in active_roots],
                      automatic_entries=[{'entry_id': e['entry_id'], 'reason': e['memory_annotation']['reason'],
                                          'root_entry_id': chain_root(e, session),
                                          'level': GRADES[e['memory_annotation']['reason']], 'dismissed': chain_root(e, session) in config['dismissed_auto_root_ids']}
                                         for e in visible if e.get('memory_annotation') and chain_root(e, session)])
    return result


def select_memory(session, current_input):
    query = set(units(current_input))
    order = {t['turn_id']: i for i, t in enumerate(session['turns'])}
    candidates = valid_candidates(session)
    scores = {e['entry_id']: len(query.intersection(units(e['content'], limit=None))) for e in candidates}
    roots = {e['entry_id']: root_for(e, session) for e in candidates}
    config = settings(session)
    grades = automatic_grades(session, candidates, config.get('dismissed_auto_root_ids', []))
    ordinary_key = lambda e: (-scores[e['entry_id']], -order[e['created_turn_id']], e['entry_id'])
    automatic = sorted([e for e in candidates if not roots[e['entry_id']] and e['entry_id'] in grades],
                       key=lambda e: (grades[e['entry_id']] != 'important', *ordinary_key(e)))[:16]
    priority_ids = {e['entry_id'] for e in automatic}
    tier = lambda e: 0 if roots[e['entry_id']] else 1 if e['entry_id'] in priority_ids and grades[e['entry_id']] == 'important' else 2 if e['entry_id'] in priority_ids else 3
    candidates.sort(key=lambda e: (tier(e), *ordinary_key(e)))
    selected, intents = [], 0
    for entry in candidates:
        if entry['kind'] == 'intent':
            if intents == 8:
                continue
            intents += 1
        if len(selected) < 32:
            selected.append(entry)
    return selected, [{'entry_id': e['entry_id'], 'reason': 'important' if roots[e['entry_id']] else 'auto_important' if tier(e) == 1 else 'auto_highlight' if tier(e) == 2 else 'related' if scores[e['entry_id']] else 'recent'}
                      for e in candidates if public(e, session)]


def final_report(candidates, selected_ids, final_ids):
    return {'entries': [dict(e, state='sent' if e['entry_id'] in final_ids else 'budget' if e['entry_id'] in selected_ids else 'not_selected') for e in candidates]}
