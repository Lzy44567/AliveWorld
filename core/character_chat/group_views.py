"""Public schema2 records. Never project candidates or synthetic old turns."""
import copy

from .models import CharacterSessionError, profile_projection, canonical_id
from .group_records import active_groups, pending_inputs, unread_messages, conversation_projection, formal_messages
from .group_lifecycle import busy
from .preferences import session_settings
from .memory import public_state
from .contract import public_ledger
from .notices import notice_for


def public_group(group):
    keys = ('group_id', 'action_id', 'request_id', 'input_ids', 'status', 'display_mode',
            'mode_at_generation', 'delivered_count', 'created_at', 'committed_revision', 'error_code')
    result = {k: copy.deepcopy(group[k]) for k in keys if k in group}
    result['origin'] = group.get('origin', 'reply')
    result['bubbles'] = copy.deepcopy(group['bubbles'][:group['delivered_count']])
    if group['status'] == 'complete' and group.get('memory_notice'):
        result['memory_notice'] = copy.deepcopy(group['memory_notice'])
    return result


def group_page(session, before=None, limit=20):
    if type(limit) is not int or not 1 <= limit <= 50:
        raise CharacterSessionError('INVALID_REQUEST')
    groups = [g for g in active_groups(session) if g['status'] in {'complete', 'partial_failed', 'generating', 'delivering'}]
    if before:
        canonical_id(before)
        index = next((i for i, g in enumerate(groups) if g['group_id'] == before), None)
        if index is None:
            raise CharacterSessionError('REVISION_CONFLICT')
        groups = groups[:index]
    page = groups[-limit:]
    ids = {mid for g in page for mid in g['input_ids']} | {
        b['message']['message_id'] for g in page for b in g['bubbles'][:g['delivered_count']]}
    return {'schema_version': 2, 'session_id': session['session_id'], 'revision': session['revision'],
            'groups': [public_group(g) for g in page],
            'messages': [r for r in conversation_projection(session) if r['message']['message_id'] in ids],
            'next_cursor': page[0]['group_id'] if len(groups) > limit else None}


def action_view(session, action, request_id=None):
    attempt = None
    if request_id:
        attempt = next((t for t in action['attempts'] if t['request_id'] == request_id), None)
        if attempt is None:
            raise CharacterSessionError('ACTION_NOT_FOUND')
    group_id = (attempt.get('group_id') or attempt.get('legacy_execution', {}).get('group_id')) if attempt else (
        action.get('resolved_by_group_id') or action.get('result_group_id'))
    group = next((g for g in session['groups'] if g['group_id'] == group_id), None)
    if attempt and group is None:
        group = next((g for g in session['groups'] if g['request_id'] == attempt['request_id']), None)
    if attempt is None and group is None and action.get('input_id'):
        group = next((g for g in reversed(active_groups(session)) if action['input_id'] in g['input_ids']
                      and g['status'] in {'generating', 'delivering', 'complete', 'partial_failed'}), None)
    if attempt is None:
        if group and action['operation'] == 'send' and (not action['attempts'] or group['action_id'] != action['action_id']):
            owner = next(a for a in session['requests'] if a['action_id'] == group['action_id'])
            attempt = next(t for t in owner['attempts'] if t['request_id'] == group['request_id'])
        elif action['attempts']:
            attempt = action['attempts'][-1]
    result = {'session_id': session['session_id'], 'action_id': action['action_id'], 'operation': action['operation'],
              'revision': session['revision'], 'result_state': action['result_state'],
              'status': attempt['status'] if attempt else 'queued', 'retryable': False}
    if attempt:
        for key in ('request_id', 'base_revision', 'committed_revision', 'error_code'):
            if key in attempt:
                result[key] = attempt[key]
        if not group:
            gid = attempt.get('group_id') or attempt.get('legacy_execution', {}).get('group_id')
            group = next((g for g in session['groups'] if g['group_id'] == gid), None)
            if gid:
                result['group_id'] = gid
        # Error classification alone is not authority to execute an old retry.
        if attempt['status'] in {'failed', 'cancelled', 'interrupted'}:
            from .legacy_lifecycle import require_legacy_retry
            from .group_lifecycle import require_group_retry
            try:
                check = require_legacy_retry if attempt.get('legacy_attempt') else require_group_retry
                check(session, action, attempt['request_id'])
                result['retryable'] = True
            except CharacterSessionError:
                pass
        snapshot = action.get('legacy_retry_snapshot')
        if attempt.get('legacy_attempt') and attempt['status'] in {'failed', 'cancelled', 'interrupted'} and snapshot:
            result['retry_input'] = snapshot['content']
            if snapshot.get('ooc_note'):
                result['retry_ooc_note'] = snapshot['ooc_note']
    if group:
        result.update(group_id=group['group_id'], group_status=group['status'])
        result['origin'] = group.get('origin', 'reply')
        if group.get('origin') == 'proactive':
            result['input_ids'] = []
    if action.get('resolved_by_group_id'):
        result['resolved_by_group_id'] = action['resolved_by_group_id']
    if action.get('input_id'):
        result['input_ids'] = group['input_ids'][:] if group else [action['input_id']]
    notice = notice_for(session, action) if not request_id or action['attempts'] and attempt is action['attempts'][-1] else None
    if notice:
        result['memory_notice'] = notice
    return result


def public_session(session, *, detail=True):
    from .proactive_contact import settings as proactive_settings
    group = busy(session)
    result = {k: session[k] for k in ('session_id', 'title', 'revision', 'presentation_mode', 'created_at', 'updated_at')}
    result.update(schema_version=2, preference_settings=session_settings(session), memory_settings=public_state(session),
                  proactive_contact=proactive_settings(session),
                  participants=[{k: copy.deepcopy(p[k]) for k in ('instance_id', 'controller', 'display_name')}
                                | {'profile_snapshot': profile_projection(p, detail=True)} for p in session['participants']],
                  world_binding=None if not session['world_binding'] else {'name': session['world_binding']['snapshot'].get('name', '')},
                  read_ai_seq=session['read_ai_seq'], unread_count=len(unread_messages(session)), queued_count=len(pending_inputs(session)),
                  busy_group=public_group(group) if group else None)
    if detail:
        result.update(group_page(session), opening=copy.deepcopy(session.get('opening')), ledger=public_ledger(session))
        rows = {r['message']['message_id']: r for r in result['messages']}
        pending = {i['input_id'] for i in pending_inputs(session)}
        rows.update({r['message']['message_id']: r for r in conversation_projection(session) if r['message']['message_id'] in pending})
        result['messages'] = sorted(rows.values(), key=lambda r: r['message']['seq'])
        failures = [a for a in session['requests'] if a['attempts'] and a['attempts'][-1]['status'] in {'failed', 'cancelled', 'interrupted'}
                    and not a.get('resolved_by_group_id') and a['result_state'] is None]
        result['last_failed_action'] = action_view(session, failures[-1]) if failures else None
    return result


def session_summary(session):
    from .proactive_contact import settings as proactive_settings
    messages = sorted(formal_messages(session).values(), key=lambda m: m['seq'])
    ai = next(p for p in session['participants'] if p['controller'] == 'ai')
    last = messages[-1] if messages else session.get('opening')
    last_ai = next((m for m in reversed(messages) if m['speaker_instance_id'] == ai['instance_id']), None)
    owner = next((g for g in active_groups(session) if last_ai and any(b['message']['message_id'] == last_ai['message_id']
                   for b in g['bubbles'][:g['delivered_count']])), None)
    group = busy(session)
    result = {k: session[k] for k in ('session_id', 'title', 'revision', 'presentation_mode', 'created_at')}
    result.update(schema_version=2, ai_name=ai['display_name'], proactive_contact=proactive_settings(session),
                  last_activity_at=last['created_at'] if last else session['created_at'],
                  last_message_preview=' '.join(last['content'].split())[:160] if last else '',
                  last_message_kind=('ai_reply' if last['speaker_instance_id'] == ai['instance_id'] else 'user_input') if messages else 'author_opening' if last else None,
                  latest_ai_message_id=last_ai['message_id'] if last_ai else None,
                  latest_ai_committed_revision=owner.get('committed_revision') if owner else None,
                  read_ai_seq=session['read_ai_seq'], unread_count=len(unread_messages(session)), queued_count=len(pending_inputs(session)),
                  busy_group=public_group(group) if group else None, pending=None)
    return result
