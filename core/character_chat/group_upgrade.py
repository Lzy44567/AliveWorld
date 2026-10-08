"""Explicit backed-up storage upgrade; never called by reads or startup.

The caller must select a session and confirm its revision and original SHA256.
No player directory discovery, provider call, API or automatic migration here.
"""
import hashlib
import json
import os
import re
from contextlib import suppress
from uuid import uuid4

from .group_migration import convert_legacy_session
from .group_schema import validate_schema2
from .models import CharacterSessionError, MAX_FILE_BYTES, canonical_id, validate_session
from .repository import _reject_constant, _unique_object


def upgrade_session(repository, session_id, *, expected_revision, expected_sha256):
    """Back up exact original bytes before an atomic, validated replacement.

    Backups are local private files under .upgrade-backups, not session records.
    A successful backup remains even if conversion/replacement subsequently fails.
    An already-upgraded session is a read-only no-op, including after lost response.
    The repository must be configured for both formats. Only single-process use
    under its existing aggregate lock is supported, as for ordinary writes.
    """
    canonical_id(session_id)
    if (type(expected_revision) is not int or expected_revision < 0 or
            not isinstance(expected_sha256, str) or
            not re.fullmatch(r'[0-9a-f]{64}', expected_sha256)):
        raise CharacterSessionError('INVALID_REQUEST')
    if not {1, 2}.issubset(repository.supported_schemas):
        raise CharacterSessionError('SCHEMA_READ_ONLY')
    with repository._guard(session_id):
        path = repository._path(session_id)
        try:
            with path.open('rb') as handle:
                raw = handle.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES:
                raise CharacterSessionError('SESSION_LIMIT')
            original = json.loads(raw, object_pairs_hook=_unique_object,
                                  parse_constant=_reject_constant)
        except FileNotFoundError:
            raise CharacterSessionError('SESSION_NOT_FOUND') from None
        except (OSError, ValueError, UnicodeError, RecursionError) as exc:
            if isinstance(exc, CharacterSessionError):
                raise
            raise CharacterSessionError('SESSION_CORRUPT') from None
        if not isinstance(original, dict) or original.get('session_id') != session_id:
            raise CharacterSessionError('SESSION_CORRUPT')
        if original.get('deleted') is True:
            raise CharacterSessionError('SESSION_DELETED')
        if original.get('schema_version') == 2:
            validate_schema2(original)
            return {'session_id': session_id, 'schema_version': 2,
                    'revision': original['revision'], 'changed': False}
        validate_session(original)
        digest = hashlib.sha256(raw).hexdigest()
        if original['revision'] != expected_revision or digest != expected_sha256:
            raise CharacterSessionError('REVISION_CONFLICT')
        if any(attempt['status'] == 'pending' for action in original['requests']
               for attempt in action['attempts']):
            # A worker may still own the old schema. Never convert under it.
            raise CharacterSessionError('SESSION_BUSY')

        directory = repository.directory / '.upgrade-backups'
        backup = directory / f'{session_id}.{digest}.{uuid4()}.schema1.bak'
        created = False
        try:
            if directory.is_symlink():
                raise OSError('unsafe backup directory')
            directory.mkdir(exist_ok=True)
            if directory.resolve().parent != repository.directory:
                raise OSError('unsafe backup directory')
            with backup.open('xb') as handle:
                created = True
                handle.write(raw)
                handle.flush()
                # Exact bytes, not normalized/reserialized JSON.
                os.fsync(handle.fileno())
        except OSError:
            if created:
                with suppress(OSError):
                    backup.unlink(missing_ok=True)
            raise CharacterSessionError('BACKUP_FAILED') from None

        converted = convert_legacy_session(original)
        repository._validate(converted)
        # Detect edits outside the cooperative in-process lock before replacement.
        try:
            if repository._path(session_id).read_bytes() != raw:
                raise CharacterSessionError('REVISION_CONFLICT')
        except OSError:
            raise CharacterSessionError('PERSISTENCE_FAILED') from None
        repository._write(converted)
        return {'session_id': session_id, 'schema_version': 2,
                'revision': converted['revision'], 'changed': True,
                'backup_name': backup.name, 'original_sha256': digest}
