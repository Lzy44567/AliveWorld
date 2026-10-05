"""Explicit user memory settings mutations, independent of generation orchestration."""
from .models import CharacterSessionError, canonical_id
from .memory import settings, valid_candidates, public
from .annotations import chain_root
from .notices import notice_for


def enable(session, enabled):
    if enabled is not True:
        raise CharacterSessionError('INVALID_REQUEST')
    value = settings(session)
    if value['version'] == 2:
        return False
    value.update(version=2, dismissed_auto_root_ids=[], notice_ack_revision=0)
    session['extensions']['character_memory'] = value
    return True


def require_v2(session):
    value = settings(session)
    if value['version'] != 2:
        raise CharacterSessionError('INVALID_REQUEST')
    return value


def selection(session, entry_id, dismissed):
    canonical_id(entry_id)
    if type(dismissed) is not bool:
        raise CharacterSessionError('INVALID_REQUEST')
    value = require_v2(session)
    entry = next((e for e in valid_candidates(session) if e['entry_id'] == entry_id and public(e, session) and e.get('memory_annotation')), None)
    root = chain_root(entry, session) if entry else None
    if not root:
        raise CharacterSessionError('INVALID_REQUEST')
    ids = value['dismissed_auto_root_ids']
    if dismissed and root not in ids:
        if len(ids) == 128:
            raise CharacterSessionError('MEMORY_DISMISS_LIMIT')
        ids.append(root)
    elif not dismissed and root in ids:
        ids.remove(root)
    else:
        return False
    session['extensions']['character_memory'] = value
    return True


def release(session, root_entry_id):
    canonical_id(root_entry_id)
    value = require_v2(session)
    ids = value['dismissed_auto_root_ids']
    active_roots = {chain_root(e, session) for e in valid_candidates(session)}
    if root_entry_id not in ids or root_entry_id in active_roots or None in active_roots:
        raise CharacterSessionError('INVALID_REQUEST')
    ids.remove(root_entry_id)
    session['extensions']['character_memory'] = value
    return True


def acknowledge(session, action_id):
    canonical_id(action_id)
    value = require_v2(session)
    action = next((a for a in session['requests'] if a['action_id'] == action_id), None)
    if not action or action['operation'] != 'send':
        raise CharacterSessionError('INVALID_REQUEST')
    turn = next((t for t in session['turns'] if t['turn_id'] == action.get('result_turn_id')), action.get('archived_turn'))
    if not turn or not turn.get('memory_notice'):
        raise CharacterSessionError('INVALID_REQUEST')
    notice = notice_for(session, action)
    if not notice or notice['committed_revision'] <= value['notice_ack_revision']:
        return False
    value['notice_ack_revision'] = notice['committed_revision']
    session['extensions']['character_memory'] = value
    return True
