"""Rebuildable session-local structural index; ledger remains the fact owner."""
from .annotations import chain_root
from .memory import valid_candidates, formal_messages, public


def index_entries(session):
    messages = formal_messages(session)
    by_id, cache = {e['entry_id']: e for e in session['ledger']}, {}
    result = []
    for entry in valid_candidates(session):
        source = entry['source']
        if source['type'] != 'author':
            audience = set(entry['visibility']['audience_instance_ids'])
            if not source['message_ids'] or any(not audience <= set(messages[mid]['visibility']['audience_instance_ids']) for mid in source['message_ids']):
                continue
            if not source['evidence'] or any(e['message_id'] not in source['message_ids'] or e['quote'] not in messages[e['message_id']]['content'] for e in source['evidence']):
                continue
        root = chain_root(entry, session, by_id=by_id, cache=cache)
        if root is None:
            continue
        result.append({'entry_id': entry['entry_id'], 'subject_instance_id': entry['subject_instance_id'],
                       'about_instance_id': entry.get('about_instance_id'), 'kind': entry['kind'],
                       'basis': source['type'], 'message_ids': list(source['message_ids']),
                       'root_entry_id': root, 'supersedes_entry_id': entry.get('supersedes_entry_id'),
                       'annotation_reason': entry.get('memory_annotation', {}).get('reason')})
    return result


def public_index(session):
    public_ids = {e['entry_id'] for e in session['ledger'] if public(e, session)}
    keys = {'entry_id', 'about_instance_id', 'kind', 'basis', 'root_entry_id', 'supersedes_entry_id', 'annotation_reason'}
    return {'version': 1, 'session_id': session['session_id'], 'revision': session['revision'],
            'entries': [{k: v for k, v in row.items() if k in keys} for row in index_entries(session) if row['entry_id'] in public_ids]}
