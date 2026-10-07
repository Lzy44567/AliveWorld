"""Public notification proof derived from committed turns, never previews."""
import copy


def completed_record(session, action):
    if session.get('schema_version') == 2:
        return next((g for g in session['groups'] if g['group_id'] == action.get('result_group_id')
                     and g['status'] == 'complete'), None)
    return next((t for t in session['turns'] if t['turn_id'] == action.get('result_turn_id')), None)


def attach_notice(session, record, action, query):
    """Derived only at final settlement; candidate messages cannot notify."""
    if action['operation'] != 'send':
        return
    from .memory import select_memory, public
    _, report = select_memory(session, query)
    selected = {e['entry_id'] for e in report if e['reason'] in {'auto_important', 'auto_highlight'}}
    ids = [e['entry_id'] for e in session['ledger'] if e['entry_id'] in record['ledger_inverse']['added_entry_ids']
           and e['entry_id'] in selected and not e.get('supersedes_entry_id') and public(e, session)]
    if ids:
        record['memory_notice'] = {'action_id': action['action_id'], 'committed_revision': record['committed_revision'], 'entry_ids': ids}


def notice_for(session, action):
    if action.get('operation') != 'send' or action.get('result_state') != 'active':
        return None
    turn = completed_record(session, action)
    if not turn or not turn.get('memory_notice'):
        return None
    notice = turn['memory_notice']
    if notice['action_id'] != action['action_id'] or notice['committed_revision'] != turn['committed_revision']:
        return None
    public_ids = {p['instance_id'] for p in session['participants']}
    entries = {e['entry_id']: e for e in session['ledger']}
    ids = [eid for eid in notice['entry_ids'] if eid in turn['ledger_inverse']['added_entry_ids']
           and eid in entries and entries[eid].get('memory_annotation')
           and entries[eid]['created_turn_id'] == turn.get('group_id', turn.get('turn_id'))
           and entries[eid]['status'] == 'active'
           and set(entries[eid]['visibility']['audience_instance_ids']) == public_ids]
    return dict(copy.deepcopy(notice), entry_ids=ids) if ids else None


def validate_notice(turn):
    if 'memory_notice' not in turn:
        return
    value = turn['memory_notice']
    if not isinstance(value, dict) or set(value) != {'action_id', 'committed_revision', 'entry_ids'}:
        raise ValueError('Invalid memory notice')
    ids = value['entry_ids']
    if value['action_id'] != turn['action_id'] or type(value['committed_revision']) is not int or value['committed_revision'] != turn['committed_revision']:
        raise ValueError('Invalid memory notice identity')
    if not isinstance(ids, list) or not 1 <= len(ids) <= 6 or len(set(ids)) != len(ids) or not set(ids) <= set(turn['ledger_inverse']['added_entry_ids']):
        raise ValueError('Invalid memory notice entries')
