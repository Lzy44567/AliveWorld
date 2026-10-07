"""One authoritative projection of delivered messages; candidates stay private."""
import copy

CURRENT_GROUP_STATES = {'generating', 'delivering', 'complete', 'failed', 'cancelled', 'interrupted', 'partial_failed'}


def active_groups(session):
    return [g for g in session['groups'] if g['status'] in CURRENT_GROUP_STATES]


def capacity_groups(session):
    # Failed attempts are archives bounded by attempts/actions/file size, not
    # successful conversation turns consuming the player's 512-group budget.
    replacing = {a.get('target_group_id') for a in session['requests'] if a['operation'] == 'regenerate'
                 and any(t['status'] == 'pending' for t in a['attempts'])}
    return [g for g in session['groups'] if g['status'] in {'generating', 'delivering', 'complete', 'partial_failed'}
            and g['group_id'] not in replacing]


def formal_messages(session):
    messages = {i['input_id']: i['message'] for i in session['inputs'] if i['status'] == 'active'}
    for group in active_groups(session):
        for bubble in group['bubbles'][:group['delivered_count']]:
            message = bubble['message']
            messages[message['message_id']] = message
    return messages


def conversation_projection(session):
    messages = formal_messages(session)
    memberships = {b['message']['message_id']: g['group_id'] for g in active_groups(session)
                   for b in g['bubbles'][:g['delivered_count']]}
    inputs = {i['input_id']: i for i in session['inputs'] if i['status'] == 'active'}
    rows = []
    for message in sorted(messages.values(), key=lambda m: m['seq']):
        row = {'message': copy.deepcopy(message), 'group_id': memberships.get(message['message_id'])}
        entry = inputs.get(message['message_id'])
        if entry and entry.get('ooc_note'):
            row['ooc_note'] = entry['ooc_note']
        rows.append(row)
    return rows


def pending_inputs(session):
    resolved = {mid for g in active_groups(session) if g['status'] in {'complete', 'partial_failed'} for mid in g['input_ids']}
    claimed = {mid for g in active_groups(session) if g['status'] in {'generating', 'delivering'} for mid in g['input_ids']}
    return sorted([i for i in session['inputs'] if i['status'] == 'active' and i['input_id'] not in resolved | claimed],
                  key=lambda i: i['message']['seq'])


def unread_messages(session):
    ai = next(p['instance_id'] for p in session['participants'] if p['controller'] == 'ai')
    return [m for m in formal_messages(session).values()
            if m['speaker_instance_id'] == ai and m['seq'] > session['read_ai_seq']]
