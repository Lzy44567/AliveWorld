"""Author openings are frozen context, never runtime message evidence."""
from uuid import UUID, uuid4

FIELDS = {'version', 'opening_id', 'source_type', 'speaker_instance_id', 'content', 'created_at'}


def normalize_opening(value):
    if not isinstance(value, str) or len(value) > 8000:
        raise ValueError('Invalid opening text')
    return value if value.strip() else ''


def make_opening(content, speaker, created_at):
    content = normalize_opening(content)
    return None if not content else dict(version=1, opening_id=str(uuid4()), source_type='author_opening',
                                        speaker_instance_id=speaker, content=content, created_at=created_at)


def validate_opening(value, speaker, created_at, reserved_ids=()):
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError('Invalid opening object')
    oid = value['opening_id']
    if (type(value['version']) is not int or value['version'] != 1 or
            value['source_type'] != 'author_opening' or value['speaker_instance_id'] != speaker or
            value['created_at'] != created_at or not normalize_opening(value['content']) or
            not isinstance(oid, str) or str(UUID(oid)) != oid or oid in reserved_ids):
        raise ValueError('Invalid opening identity')


def opening_context(value):
    return None if value is None else {key: value[key] for key in ('source_type', 'speaker_instance_id', 'content')}
