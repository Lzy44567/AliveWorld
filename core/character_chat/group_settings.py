"""Schema2 context mutations, separate from generation and HTTP projections."""
import copy

from .models import CharacterSessionError, text, canonical_id
from .group_lifecycle import check_revision, busy
from .group_records import pending_inputs
from .preferences import validate_settings
from .memory import valid_candidates, public, formal_messages
from . import memory_operations


def context_writable(session, revision):
    check_revision(session, revision)
    if busy(session) or pending_inputs(session):
        raise CharacterSessionError('SESSION_BUSY')


def metadata(session, revision, title=None, presentation_mode=None, preference_settings=None):
    if title is None and presentation_mode is None and preference_settings is None:
        raise CharacterSessionError('INVALID_REQUEST')
    if title is not None:
        text(title, 80)
    if presentation_mode is not None and (not isinstance(presentation_mode, str) or presentation_mode not in {'messenger', 'roleplay'}):
        raise CharacterSessionError('INVALID_REQUEST')
    if preference_settings is not None:
        try:
            preference_settings = validate_settings(preference_settings)
        except ValueError:
            raise CharacterSessionError('INVALID_REQUEST') from None
    context_change = presentation_mode is not None or preference_settings is not None
    if context_change:
        context_writable(session, revision)
    else:
        check_revision(session, revision)
    if title is not None:
        session['title'] = title
    if presentation_mode is not None:
        session['presentation_mode'] = presentation_mode
    if preference_settings is not None:
        session['extensions']['character_preferences'] = copy.deepcopy(preference_settings)
    session['revision'] += 1
    if context_change:
        session['context_epoch'] += 1
    return True


def mark_memory(session, revision, entry_id, important):
    context_writable(session, revision)
    changed = memory_operations.mark(session, entry_id, important)
    if changed:
        session['revision'] += 1
        session['context_epoch'] += 1
    return changed


def update_memory(session, revision, operation, *args):
    if operation not in {'enable', 'selection', 'release', 'acknowledge'}:
        raise CharacterSessionError('INVALID_REQUEST')
    if operation == 'acknowledge':
        check_revision(session, revision)
    else:
        context_writable(session, revision)
    changed = getattr(memory_operations, operation)(session, *args)
    if changed:
        session['revision'] += 1
        if operation != 'acknowledge':
            session['context_epoch'] += 1
    return changed


def memory_sources(session, entry_id):
    canonical_id(entry_id)
    entry = next((e for e in valid_candidates(session) if e['entry_id'] == entry_id and public(e, session)), None)
    if entry is None:
        raise CharacterSessionError('INVALID_REQUEST')
    messages = formal_messages(session)
    audience = {p['instance_id'] for p in session['participants']}
    selected = [messages[mid] for mid in entry['source']['message_ids']]
    if any(set(m['visibility']['audience_instance_ids']) != audience for m in selected):
        raise CharacterSessionError('INVALID_REQUEST')
    return {'entry_id': entry_id, 'revision': session['revision'], 'messages': [
        {k: copy.deepcopy(m[k]) for k in ('message_id', 'speaker_instance_id', 'content')} for m in selected]}
