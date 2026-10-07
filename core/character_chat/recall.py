"""Bounded linked-source groups and monotone final evidence closure."""
import copy
from .cognition import index_entries
from .memory import formal_messages, units, public

MESSAGE_FIELDS = ('message_id', 'turn_id', 'speaker_instance_id', 'content', 'presentation_mode', 'visibility', 'created_at')


def project_message(message):
    fields = (*MESSAGE_FIELDS, 'seq') if 'seq' in message else MESSAGE_FIELDS
    return {key: copy.deepcopy(message[key]) for key in fields if key in message}


def recall_candidates(session, ledger, current_input, initial_history):
    query = set(units(current_input))
    rows = {row['entry_id']: row for row in index_entries(session)}
    messages = formal_messages(session)
    history_ids = {m['message_id'] for m in initial_history}
    groups, selected, characters = [], set(), 0
    for entry in ledger:
        row = rows.get(entry['entry_id'])
        if not query or not row or row['basis'] == 'author' or not query.intersection(units(entry['content'], limit=None)):
            continue
        refs = row['message_ids']
        pending_ids = [mid for mid in refs if mid not in history_ids]
        if not pending_ids:
            continue
        added = [mid for mid in pending_ids if mid not in selected]
        size = sum(len(messages[mid]['content']) for mid in added)
        accepted = len(selected) + len(added) <= 4 and characters + size <= 4000
        groups.append({'entry_id': entry['entry_id'], 'refs': refs, 'messages': [project_message(messages[mid]) for mid in pending_ids],
                       'public': public(entry, session), 'initial': accepted, 'active': accepted})
        if accepted:
            selected.update(added)
            characters += size
    return groups


def close_groups(groups, history, ledger):
    """In-place monotone removal; never promote a previously skipped group."""
    history_ids = {m['message_id'] for m in history}
    entry_ids = {e['entry_id'] for e in ledger}
    for _ in range(len(groups) + 1):
        projected_ids = {m['message_id'] for g in groups if g['active'] for m in g['messages']}
        available = history_ids | projected_ids
        changed = False
        for group in groups:
            if group['active'] and (group['entry_id'] not in entry_ids or not set(group['refs']) <= available):
                group['active'] = False
                changed = True
        if not changed:
            break
    supported = {m['message_id'] for g in groups if g['active'] for m in g['messages']}
    sources, seen = [], set()
    for group in groups:
        if group['initial']:
            for message in group['messages']:
                if message['message_id'] in supported and message['message_id'] not in seen:
                    sources.append(message)
                    seen.add(message['message_id'])
    return sources


def trim_group(groups):
    for group in reversed(groups):
        if group['active']:
            group['active'] = False
            return True
    return False


def public_report(groups):
    return {'version': 1, 'entries': [{'entry_id': g['entry_id'],
            'state': 'sent' if g['active'] else 'budget' if g['initial'] else 'limit'} for g in groups if g['public']]}


def evidence_messages(history, recalled):
    by_id = {}
    for message in [*history, *recalled]:
        by_id.setdefault(message['message_id'], message)
    return list(by_id.values())
