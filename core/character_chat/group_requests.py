"""Request-boundary normalization; domain lifecycle consumes these values."""
from .models import CharacterSessionError, canonical_id, text
from .ooc import normalize_ooc, OocInputError


def send_values(payload):
    if (not isinstance(payload, dict) or
            not {'client_action_id', 'expected_revision', 'content'} <= set(payload) or
            not set(payload) <= {'client_action_id', 'expected_revision', 'content', 'ooc_note'}):
        raise CharacterSessionError('INVALID_REQUEST')
    aid = canonical_id(payload['client_action_id'])
    content = text(payload['content'], 4000).strip()
    try:
        note = normalize_ooc(payload.get('ooc_note'))
    except OocInputError as exc:
        raise CharacterSessionError(exc.code) from None
    return aid, content, note


def batch_values(payload, display_mode):
    if (not isinstance(payload, dict) or
            set(payload) != {'client_action_id', 'expected_revision', 'operation', 'target_group_id'}):
        raise CharacterSessionError('INVALID_REQUEST')
    aid, gid = canonical_id(payload['client_action_id']), canonical_id(payload['target_group_id'])
    if payload['operation'] not in {'undo', 'regenerate'} or display_mode not in {'stream', 'gaps', 'instant'}:
        raise CharacterSessionError('INVALID_REQUEST')
    return aid, gid


def retry_values(payload):
    if not isinstance(payload, dict) or set(payload) != {'expected_revision', 'retry_of', 'retry_token'}:
        raise CharacterSessionError('INVALID_REQUEST')
    canonical_id(payload['retry_of'])
    canonical_id(payload['retry_token'])
