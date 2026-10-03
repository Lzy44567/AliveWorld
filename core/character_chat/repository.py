"""Atomic local persistence, separate from story saves and reusable cards."""

from __future__ import annotations

import copy
import json
import os
import tempfile
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

from core.session_manager import mutation_guard
from .models import (CharacterSessionError, MAX_FILE_BYTES, canonical_id,
                     json_bytes, validate_session)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CharacterSessionError("SESSION_CORRUPT")
        result[key] = value
    return result


def _reject_constant(_):
    raise CharacterSessionError("SESSION_CORRUPT")


class CharacterSessionRepository:
    """Single-process repository. Callers receive detached authoritative copies."""

    def __init__(self, directory: Path):
        self.directory = Path(directory).resolve()

    def _path(self, session_id: str) -> Path:
        canonical_id(session_id)
        path = self.directory / f"{session_id}.json"
        if path.is_symlink():
            raise CharacterSessionError("SESSION_CORRUPT")
        return path

    def _guard(self, session_id: str):
        return mutation_guard("character-storage", str(self.directory / session_id), blocking=True)

    def _load(self, session_id: str) -> dict:
        path = self._path(session_id)
        try:
            with path.open("rb") as handle:
                raw = handle.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES:
                raise CharacterSessionError("SESSION_LIMIT")
            value = json.loads(raw, object_pairs_hook=_unique_object,
                               parse_constant=_reject_constant)
        except FileNotFoundError:
            raise CharacterSessionError("SESSION_NOT_FOUND") from None
        except (OSError, UnicodeError, ValueError, RecursionError) as exc:
            if isinstance(exc, CharacterSessionError):
                raise
            raise CharacterSessionError("SESSION_CORRUPT") from None
        if not isinstance(value, dict) or value.get("session_id") != session_id:
            raise CharacterSessionError("SESSION_CORRUPT")
        return value

    def load(self, session_id: str) -> dict:
        with self._guard(canonical_id(session_id)):
            value = self._load(session_id)
            if value.get("deleted") is True:
                raise CharacterSessionError("SESSION_DELETED")
            # Preserve unknown future schemas for read-only inspection, never downgrade.
            if type(value.get("schema_version")) is int and value["schema_version"] > 1:
                return copy.deepcopy(value)
            try:
                validate_session(value)
            except CharacterSessionError:
                raise CharacterSessionError("SESSION_CORRUPT") from None
            return copy.deepcopy(value)

    def _write(self, value: dict) -> None:
        validate_session(value)
        raw = json_bytes(value)
        if len(raw) > MAX_FILE_BYTES:
            raise CharacterSessionError("SESSION_LIMIT")
        path = self._path(value["session_id"])
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=self.directory, prefix=".character-",
                                              suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError:
            raise CharacterSessionError("PERSISTENCE_FAILED") from None
        finally:
            if temporary is not None:
                with suppress(OSError):
                    temporary.unlink(missing_ok=True)

    def create(self, candidate: dict) -> dict:
        value = copy.deepcopy(candidate)
        validate_session(value)
        if value.get("deleted") or value.get("revision") != 0:
            raise CharacterSessionError("INVALID_REQUEST")
        session_id = value["session_id"]
        with self._guard(session_id):
            try:
                existing = self._load(session_id)
            except CharacterSessionError as exc:
                if exc.code != "SESSION_NOT_FOUND":
                    raise
            else:
                if existing.get("deleted") is True:
                    raise CharacterSessionError("SESSION_DELETED")
                if existing.get("schema_version") != 1:
                    raise CharacterSessionError("SCHEMA_READ_ONLY")
                validate_session(existing)
                if existing.get("creation_fingerprint") != value["creation_fingerprint"]:
                    raise CharacterSessionError("IDEMPOTENCY_MISMATCH")
                return copy.deepcopy(existing)
            self._write(value)
            return copy.deepcopy(value)

    def save(self, candidate: dict, *, expected_revision: int) -> dict:
        value = copy.deepcopy(candidate)
        validate_session(value)
        if value.get("deleted") or type(expected_revision) is not int:
            raise CharacterSessionError("INVALID_REQUEST")
        with self._guard(value["session_id"]):
            old = self._load(value["session_id"])
            if old.get("deleted") is True:
                raise CharacterSessionError("SESSION_DELETED")
            validate_session(old)
            if old["revision"] != expected_revision:
                raise CharacterSessionError("REVISION_CONFLICT")
            if value["revision"] != expected_revision + 1:
                raise CharacterSessionError("REVISION_CONFLICT")
            for key in ("participants", "world_binding", "creation_fingerprint", "created_at", "opening"):
                if old.get(key) != value.get(key):
                    raise CharacterSessionError("PROFILE_FROZEN")
            value["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._write(value)
            return copy.deepcopy(value)

    def transaction(self, session_id: str, operation):
        """Short aggregate lock; request states need not advance domain revision."""
        with self._guard(canonical_id(session_id)):
            old = self._load(session_id)
            if old.get('deleted') is True:
                raise CharacterSessionError('SESSION_DELETED')
            validate_session(old)
            candidate = copy.deepcopy(old)
            result, changed = operation(candidate)
            if changed:
                if candidate['revision'] not in (old['revision'], old['revision'] + 1):
                    raise CharacterSessionError('REVISION_CONFLICT')
                for key in ('participants', 'world_binding', 'creation_fingerprint', 'created_at', 'opening'):
                    if candidate.get(key) != old.get(key):
                        raise CharacterSessionError('PROFILE_FROZEN')
                candidate['updated_at'] = datetime.now(timezone.utc).isoformat()
                self._write(candidate)
            return copy.deepcopy(result)

    def session_ids(self):
        if not self.directory.exists():
            return []
        ids = []
        for path in self.directory.glob('*.json'):
            try:
                ids.append(canonical_id(path.stem))
            except CharacterSessionError:
                continue
        return sorted(ids)

    def delete(self, session_id: str, *, expected_revision: int) -> None:
        canonical_id(session_id)
        if type(expected_revision) is not int:
            raise CharacterSessionError("INVALID_REQUEST")
        with self._guard(session_id):
            old = self._load(session_id)
            if old.get("deleted") is True:
                return
            validate_session(old)
            if old["revision"] != expected_revision:
                raise CharacterSessionError("REVISION_CONFLICT")
            if any(a.get('status') == 'pending' for action in old['requests'] for a in action.get('attempts', [])):
                raise CharacterSessionError('SESSION_BUSY')
            self._write({"schema_version": 1, "session_id": session_id, "deleted": True})
