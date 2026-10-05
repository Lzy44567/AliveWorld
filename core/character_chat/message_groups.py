"""Bounded v3 output identities; no persistence or implicit old-session migration."""
import copy
from uuid import UUID

from .models import CharacterSessionError, text

MAX_BUBBLES = 6
MAX_GROUP_CHARACTERS = 8000


def invalid():
    raise CharacterSessionError('CONTRACT_INVALID')


def validate_messages(messages):
    if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_BUBBLES:
        invalid()
    size = 0
    for index, message in enumerate(messages):
        if (not isinstance(message, dict) or set(message) != {'local_id', 'text'}
                or message['local_id'] != f'b{index}'):
            invalid()
        text(message['text'], MAX_GROUP_CHARACTERS)
        size += len(message['text'])
        if size > MAX_GROUP_CHARACTERS:
            invalid()
    return messages


def resolve_local_sources(result, reserved_ids):
    """Map only source identity fields, never replace arbitrary user/role text.

    All six IDs must have been allocated before the provider call. Authorization
    of each resulting source and quote remains the transaction validator's job.
    """
    messages = validate_messages(result.get('messages'))
    if not isinstance(reserved_ids, list) or len(reserved_ids) != MAX_BUBBLES:
        invalid()
    try:
        if any(not isinstance(i, str) or str(UUID(i)) != i for i in reserved_ids):
            invalid()
    except (ValueError, TypeError, AttributeError):
        invalid()
    if len(set(reserved_ids)) != MAX_BUBBLES:
        invalid()
    mapping = {m['local_id']: reserved_ids[i] for i, m in enumerate(messages)}
    resolved = copy.deepcopy(result)

    def reference(ref):
        if not isinstance(ref, str):
            invalid()
        if ref in mapping:
            return mapping[ref]
        # Local-looking references cannot masquerade as formal message IDs.
        if ref.startswith('b') and ref[1:].isdigit():
            invalid()
        return ref

    for op in resolved.get('ledger_ops', []):
        if not isinstance(op, dict):
            invalid()
        source = op.get('source')
        if not isinstance(source, dict):
            invalid()
        refs, evidence = source.get('message_ids'), source.get('evidence')
        if not isinstance(refs, list) or not isinstance(evidence, list):
            invalid()
        source['message_ids'] = [reference(ref) for ref in refs]
        for item in evidence:
            if not isinstance(item, dict) or 'message_id' not in item:
                invalid()
            item['message_id'] = reference(item['message_id'])
    return resolved, mapping
