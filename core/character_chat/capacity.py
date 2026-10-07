"""Read-only bounded diagnostic projection, never a model-call permission."""
from .models import CharacterSessionError, MAX_FILE_BYTES, json_bytes
from .limits import MAX_TURNS, MAX_LEDGER, MAX_ACTIONS, MAX_ATTEMPTS, MAX_ACTIVE, MAX_EXTENSIONS_BYTES


def pressure(used, limit):
    return 'at_limit' if used >= limit else 'near' if used * 100 >= limit * 80 else 'normal'


def capacity_report(session):
    # The repository owns validation. Never inspect unknown future schemas.
    if session.get('schema_version') != 1:
        raise CharacterSessionError('SCHEMA_READ_ONLY')
    counts = {'formal_turns': (len(session['turns']), MAX_TURNS),
              'actions': (len(session['requests']), MAX_ACTIONS),
              'attempts': (sum(len(a['attempts']) for a in session['requests']), MAX_ATTEMPTS)}
    hidden = [pressure(sum(e['status'] == 'active' for e in session['ledger']), MAX_ACTIVE),
              pressure(len(session['ledger']), MAX_LEDGER),
              pressure(len(json_bytes(session)), MAX_FILE_BYTES),
              pressure(len(json_bytes(session['extensions'])), MAX_EXTENSIONS_BYTES)]
    states = ['normal', 'near', 'at_limit']
    all_blocked = counts['actions'][0] >= MAX_ACTIONS or counts['attempts'][0] >= MAX_ATTEMPTS
    return {'session_id': session['session_id'], 'revision': session['revision'], 'version': 1,
            'public_counts': {key: {'used': used, 'limit': limit, 'state': pressure(used, limit)} for key, (used, limit) in counts.items()},
            'recording_pressure': max(hidden, key=states.index),
            'operation_capacity': {op: 'blocked' if all_blocked or (op == 'send' and counts['formal_turns'][0] >= MAX_TURNS)
                                   else 'not_known_blocked' for op in ('send', 'retry', 'regenerate', 'undo')}}


def group_capacity_report(session):
    """Explicit schema2 projection; old readers still reject schema2 by default.

    Logical groups include reserved generation/delivery slots, not individual
    bubbles. Archives still consume actions/attempts and aggregate file space.
    """
    from .group_schema import validate_schema2
    from .group_records import capacity_groups
    if session.get('schema_version') != 2:
        raise CharacterSessionError('SCHEMA_READ_ONLY')
    validate_schema2(session)
    used_groups = len(capacity_groups(session))
    counts = {'formal_groups': (used_groups, MAX_TURNS),
              'actions': (len(session['requests']), MAX_ACTIONS),
              'attempts': (sum(len(a['attempts']) for a in session['requests']), MAX_ATTEMPTS)}
    hidden = [pressure(sum(e['status'] == 'active' for e in session['ledger']), MAX_ACTIVE),
              pressure(len(session['ledger']), MAX_LEDGER), pressure(len(json_bytes(session)), MAX_FILE_BYTES),
              pressure(len(json_bytes(session['extensions'])), MAX_EXTENSIONS_BYTES)]
    all_blocked = counts['actions'][0] >= MAX_ACTIONS or counts['attempts'][0] >= MAX_ATTEMPTS
    return {'session_id': session['session_id'], 'revision': session['revision'], 'version': 2,
            'public_counts': {key: {'used': used, 'limit': limit, 'state': pressure(used, limit)} for key, (used, limit) in counts.items()},
            'recording_pressure': max(hidden, key=['normal', 'near', 'at_limit'].index),
            'operation_capacity': {op: 'blocked' if all_blocked or (op == 'send' and used_groups >= MAX_TURNS)
                                   else 'not_known_blocked' for op in ('send', 'retry', 'regenerate', 'undo')}}
