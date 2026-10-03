"""Identity and immutable creation snapshots for the character MVP."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4, uuid5


SCHEMA_VERSION = 1
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024
CREATION_NAMESPACE = UUID("765b4eca-d6d8-4edb-9522-2a81a8500a16")


class CharacterSessionError(ValueError):
    """Safe domain error; never includes private input or filesystem paths."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def canonical_id(value: str) -> str:
    try:
        parsed = str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise CharacterSessionError("INVALID_REQUEST") from None
    if parsed != value:
        raise CharacterSessionError("INVALID_REQUEST")
    return parsed


def json_bytes(value: object) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False,
                          sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise CharacterSessionError("INVALID_REQUEST") from None


def validate_depth(value: object, maximum: int, depth: int = 0) -> None:
    if depth > maximum:
        raise CharacterSessionError("INPUT_LIMIT")
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise CharacterSessionError("INVALID_REQUEST")
        for child in value.values():
            validate_depth(child, maximum, depth + 1)
    elif isinstance(value, list):
        for child in value:
            validate_depth(child, maximum, depth + 1)


def text(value: object, maximum: int, *, required: bool = True) -> str:
    if not isinstance(value, str) or (required and not value.strip()):
        raise CharacterSessionError("INVALID_REQUEST")
    if len(value) > maximum:
        raise CharacterSessionError("INPUT_LIMIT")
    return value


def validate_profile(profile: dict, *, ai: bool) -> None:
    if not isinstance(profile, dict):
        raise CharacterSessionError("INVALID_REQUEST")
    validate_depth(profile, 32)
    if len(json_bytes(profile)) > MAX_SNAPSHOT_BYTES:
        raise CharacterSessionError("INPUT_LIMIT")
    text(profile.get("name"), 80)
    text(profile.get("description", ""), 32000, required=ai)
    text(profile.get("starting_scene", ""), 8000, required=False)


def validate_asset_ref(ref: object, *, required: bool) -> None:
    if ref is None and not required:
        return
    if not isinstance(ref, dict) or set(ref) != {"kind", "key"}:
        raise CharacterSessionError("INVALID_REQUEST")
    if ref["kind"] != "character":
        raise CharacterSessionError("INVALID_REQUEST")
    text(ref["key"], 1024)


def create_session(creation_id: str, ai_profile: dict, ai_asset_ref: dict,
                   *, user_profile: dict | None = None,
                   user_asset_ref: dict | None = None, title: str | None = None,
                   presentation_mode: str = "messenger") -> dict:
    """Pure construction. Source assets remain untouched and unaliased."""
    canonical_id(creation_id)
    if presentation_mode not in {"messenger", "roleplay"}:
        raise CharacterSessionError("INVALID_REQUEST")
    if (user_profile is None) != (user_asset_ref is None):
        raise CharacterSessionError("INVALID_REQUEST")
    validate_profile(ai_profile, ai=True)
    validate_asset_ref(ai_asset_ref, required=True)
    user = {"name": "我", "description": ""} if user_profile is None else user_profile
    validate_profile(user, ai=False)
    validate_asset_ref(user_asset_ref, required=False)
    title = ai_profile["name"] if title is None else title
    text(title, 80)
    creation = {"ai": ai_profile, "ai_ref": ai_asset_ref, "user": user,
                "user_ref": user_asset_ref, "title": title, "mode": presentation_mode}
    now = datetime.now(timezone.utc).isoformat()
    participants = []
    for controller, profile, ref in (("user", user, user_asset_ref),
                                     ("ai", ai_profile, ai_asset_ref)):
        participants.append({"instance_id": str(uuid4()), "controller": controller,
                             "display_name": profile["name"],
                             "asset_ref": copy.deepcopy(ref),
                             "source_hash": hashlib.sha256(json_bytes(profile)).hexdigest() if ref else None,
                             "profile_snapshot": copy.deepcopy(profile)})
    return {"schema_version": SCHEMA_VERSION,
            "session_id": str(uuid5(CREATION_NAMESPACE, creation_id)),
            "creation_fingerprint": hashlib.sha256(json_bytes(creation)).hexdigest(),
            "title": title, "revision": 0, "created_at": now, "updated_at": now,
            "presentation_mode": presentation_mode, "participants": participants,
            "world_binding": None, "turns": [], "ledger": [], "requests": [],
            "extensions": {}}


def validate_session(value: object) -> None:
    """Validate storage envelope; turn/ledger operation rules belong to next slice."""
    if not isinstance(value, dict):
        raise CharacterSessionError("SESSION_CORRUPT")
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise CharacterSessionError("SCHEMA_READ_ONLY")
    canonical_id(value.get("session_id"))
    if value.get("deleted") is True:
        if set(value) != {"schema_version", "session_id", "deleted"}:
            raise CharacterSessionError("SESSION_CORRUPT")
        return
    text(value.get("title"), 80)
    if type(value.get("revision")) is not int or value["revision"] < 0:
        raise CharacterSessionError("SESSION_CORRUPT")
    if value.get("presentation_mode") not in {"messenger", "roleplay"}:
        raise CharacterSessionError("SESSION_CORRUPT")
    participants = value.get("participants")
    if not isinstance(participants, list) or len(participants) != 2:
        raise CharacterSessionError("SESSION_CORRUPT")
    if any(not isinstance(p, dict) for p in participants):
        raise CharacterSessionError("SESSION_CORRUPT")
    if any(not isinstance(p.get("controller"), str) for p in participants):
        raise CharacterSessionError("SESSION_CORRUPT")
    if {p.get("controller") for p in participants} != {"user", "ai"}:
        raise CharacterSessionError("SESSION_CORRUPT")
    ids = [canonical_id(p.get("instance_id")) for p in participants]
    if len(set(ids)) != 2:
        raise CharacterSessionError("SESSION_CORRUPT")
    for p in participants:
        text(p.get("display_name"), 80)
        validate_profile(p.get("profile_snapshot"), ai=p["controller"] == "ai")
        validate_asset_ref(p.get("asset_ref"), required=p["controller"] == "ai")
    for key, limit in (("turns", 512), ("ledger", 2048), ("requests", 2048)):
        if not isinstance(value.get(key), list):
            raise CharacterSessionError("SESSION_CORRUPT")
        if len(value[key]) > limit:
            raise CharacterSessionError("SESSION_LIMIT")
    text(value.get("creation_fingerprint"), 64)
    text(value.get("created_at"), 64)
    text(value.get("updated_at"), 64)
    if not isinstance(value.get("extensions"), dict):
        raise CharacterSessionError("SESSION_CORRUPT")
    validate_depth(value["extensions"], 8)
    if len(json_bytes(value["extensions"])) > 32 * 1024:
        raise CharacterSessionError("SESSION_LIMIT")


def profile_projection(participant: dict) -> dict:
    """Never inject external extensions, metadata or player/NPC flags."""
    profile = participant["profile_snapshot"]
    return {key: profile.get(key, "") for key in ("name", "description", "starting_scene")}
