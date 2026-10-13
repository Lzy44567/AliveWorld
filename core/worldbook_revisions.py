"""Save-local capture history and exact, non-destructive turn rollback."""
from copy import deepcopy
from uuid import uuid4

from core.capture_source import turn_identity


def record_capture_changes(before, after, source_turn):
    """Attach entry deltas to the same book that is atomically committed."""
    if source_turn is None:
        return after
    return record_revision_changes(before, after, turn_identity(source_turn), source_turn.get('turn_id'))


def record_revision_changes(before, after, source, source_turn):
    result = deepcopy(after)
    old = {entry['id']: entry for entry in before.get('entries', [])}
    new = {entry['id']: entry for entry in result.get('entries', [])}
    changes = []
    for entry_id in dict.fromkeys([*old, *new]):
        previous, current = old.get(entry_id), new.get(entry_id)
        if previous == current:
            continue
        changes.append({
            'id': 'change_' + uuid4().hex,
            'source': source, 'source_turn': source_turn,
            'entry_id': entry_id, 'before': deepcopy(previous), 'after': deepcopy(current),
            'status': 'applied',
        })
    result.setdefault('capture_history', []).extend(changes)
    return result


def reconcile_capture_history(book, active_turns):
    """Reverse invalid source changes, keeping later independent manual edits."""
    result = deepcopy(book)
    active = {turn_identity(turn) for turn in active_turns}
    entries = {entry['id']: entry for entry in result.get('entries', [])}
    reverted, detached = [], []
    for change in reversed(result.get('capture_history', [])):
        if change['status'] != 'applied' or change['source'] in active:
            continue
        entry_id = change['entry_id']
        if entries.get(entry_id) != change['after']:
            change['status'] = 'detached'
            detached.append(change['id'])
            continue
        if change['before'] is None:
            entries.pop(entry_id, None)
        else:
            entries[entry_id] = deepcopy(change['before'])
        change['status'] = 'reverted'
        reverted.append(change['id'])
    result['entries'] = list(entries.values())
    return result, {'reverted': reverted, 'detached': detached}
