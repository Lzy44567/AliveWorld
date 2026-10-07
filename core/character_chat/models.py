"""Identity and immutable creation snapshots for the character MVP."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4, uuid5
from core.character_profiles import CharacterProfileError, ROLE_SEMANTICS, validate_role_fields, structured_projection
from .opening import make_opening, normalize_opening, validate_opening
from .preferences import validate_settings
from .memory import settings as memory_settings, MemoryVersionError
from .annotations import validate_annotation
from .protocol import attempt_contract, validate_contract, ReplyContractError, V2, V3
from .notices import validate_notice
from .context_contract import context_contract, validate_context_contract, ContextContractError, LEGACY, C3, C4
from .ooc import validate_stored_ooc
from .limits import MAX_TURNS, MAX_LEDGER, MAX_ACTIONS, MAX_ATTEMPTS, MAX_ACTIVE, MAX_EXTENSIONS_BYTES


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
                   presentation_mode: str = "messenger", opening_text: str = "") -> dict:
    """Pure construction. Source assets remain untouched and unaliased."""
    canonical_id(creation_id)
    if not isinstance(presentation_mode, str) or presentation_mode not in {"messenger", "roleplay"}:
        raise CharacterSessionError("INVALID_REQUEST")
    if (user_profile is None) != (user_asset_ref is None):
        raise CharacterSessionError("INVALID_REQUEST")
    validate_profile(ai_profile, ai=True)
    user = {"name": "我", "description": ""} if user_profile is None else user_profile
    validate_profile(user, ai=False)
    for profile in (ai_profile, user_profile):
        if profile and profile.get('role_fields') is not None:
            try:
                validate_role_fields(profile['role_fields'])
            except CharacterProfileError:
                raise CharacterSessionError('ROLE_FIELDS_INVALID') from None
    validate_asset_ref(ai_asset_ref, required=True)
    validate_asset_ref(user_asset_ref, required=False)
    title = ai_profile["name"] if title is None else title
    text(title, 80)
    creation = {"ai": ai_profile, "ai_ref": ai_asset_ref, "user": user,
                "user_ref": user_asset_ref, "title": title, "mode": presentation_mode}
    try:
        opening_text = normalize_opening(opening_text)
    except ValueError:
        raise CharacterSessionError('INVALID_REQUEST') from None
    if opening_text:
        creation['opening_text'] = opening_text
    now = datetime.now(timezone.utc).isoformat()
    participants = []
    for controller, profile, ref in (("user", user, user_asset_ref),
                                     ("ai", ai_profile, ai_asset_ref)):
        participants.append({"instance_id": str(uuid4()), "controller": controller,
                             "profile_semantics": ROLE_SEMANTICS if profile.get('role_fields') is not None else 'legacy',
                             "display_name": profile["name"],
                             "asset_ref": copy.deepcopy(ref),
                             "source_hash": hashlib.sha256(json_bytes(profile)).hexdigest() if ref else None,
                             "profile_snapshot": copy.deepcopy(profile)})
    result = {"schema_version": SCHEMA_VERSION,
            "session_id": str(uuid5(CREATION_NAMESPACE, creation_id)),
            "creation_fingerprint": hashlib.sha256(json_bytes(creation)).hexdigest(),
            "title": title, "revision": 0, "created_at": now, "updated_at": now,
            "presentation_mode": presentation_mode, "participants": participants,
            "world_binding": None, "turns": [], "ledger": [], "requests": [],
            "extensions": {'character_memory': {'version': 2, 'important_entry_ids': [],
                'dismissed_auto_root_ids': [], 'notice_ack_revision': 0}}}
    if opening_text:
        result['opening'] = make_opening(opening_text, participants[1]['instance_id'], now)
    return result


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
    validate_envelope(value)
    for key, limit in (("turns", MAX_TURNS), ("ledger", MAX_LEDGER), ("requests", MAX_ACTIONS)):
        if not isinstance(value.get(key), list):
            raise CharacterSessionError("SESSION_CORRUPT")
        if len(value[key]) > limit:
            raise CharacterSessionError("SESSION_LIMIT")
    validate_records(value)


def validate_envelope(value):
    """Shared frozen profiles/settings; no runtime messages or schema coercion."""
    text(value.get("title"), 80)
    if type(value.get("revision")) is not int or value["revision"] < 0:
        raise CharacterSessionError("SESSION_CORRUPT")
    if not isinstance(value.get('presentation_mode'), str) or value.get("presentation_mode") not in {"messenger", "roleplay"}:
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
        marker = p.get('profile_semantics', 'legacy')
        if not isinstance(marker, str) or marker not in {'legacy', ROLE_SEMANTICS}:
            raise CharacterSessionError('SCHEMA_READ_ONLY')
        if marker == ROLE_SEMANTICS:
            try:
                validate_role_fields(p['profile_snapshot'].get('role_fields'))
            except CharacterProfileError:
                raise CharacterSessionError('SESSION_CORRUPT') from None
        validate_asset_ref(p.get("asset_ref"), required=p["controller"] == "ai")
    text(value.get("creation_fingerprint"), 64)
    text(value.get("created_at"), 64)
    text(value.get("updated_at"), 64)
    if not isinstance(value.get("extensions"), dict):
        raise CharacterSessionError("SESSION_CORRUPT")
    validate_depth(value["extensions"], 8)
    try:
        memory_settings(value)
    except MemoryVersionError:
        raise CharacterSessionError('MEMORY_VERSION_UNSUPPORTED') from None
    except (ValueError, TypeError, AttributeError):
        raise CharacterSessionError('SESSION_CORRUPT') from None
    if 'character_preferences' in value['extensions']:
        try:
            validate_settings(value['extensions']['character_preferences'])
        except ValueError:
            raise CharacterSessionError('SESSION_CORRUPT') from None
    if len(json_bytes(value["extensions"])) > MAX_EXTENSIONS_BYTES:
        raise CharacterSessionError("SESSION_LIMIT")
    binding = value.get('world_binding')
    if binding is not None:
        if not isinstance(binding, dict) or set(binding) != {'asset_ref', 'source_hash', 'snapshot'}:
            raise CharacterSessionError('SESSION_CORRUPT')
        ref = binding['asset_ref']
        if not isinstance(ref, dict) or set(ref) != {'kind', 'key'} or ref.get('kind') != 'worldbook':
            raise CharacterSessionError('SESSION_CORRUPT')
        text(ref.get('key'), 1024)
        text(binding.get('source_hash'), 64)
        if not isinstance(binding.get('snapshot'), dict):
            raise CharacterSessionError('SESSION_CORRUPT')
        validate_depth(binding['snapshot'], 32)
        if len(json_bytes(binding['snapshot'])) > MAX_SNAPSHOT_BYTES:
            raise CharacterSessionError('SESSION_LIMIT')


def validate_records(value):
    """Fail closed on malformed persisted runtime records before lifecycle use."""
    try:
        participant_ids = {p['instance_id'] for p in value['participants']}
        turn_ids, action_ids, request_ids, message_ids, entry_ids = set(), set(), set(), set(), set()
        messages, inverses, turn_records = {}, [], {}
        ai_id = next(p['instance_id'] for p in value['participants'] if p['controller'] == 'ai')
        user_id = next(p['instance_id'] for p in value['participants'] if p['controller'] == 'user')
        def turn(record, *, archived=False):
            validate_stored_ooc(record)
            canonical_id(record['turn_id'])
            canonical_id(record['action_id'])
            canonical_id(record['request_id'])
            if record['turn_id'] in turn_ids:
                raise CharacterSessionError('SESSION_CORRUPT')
            turn_ids.add(record['turn_id'])
            turn_records[record['turn_id']] = record
            for key in ('user_message', 'ai_message'):
                m = record[key]
                canonical_id(m['message_id'])
                if m['message_id'] in message_ids or m['turn_id'] != record['turn_id']:
                    raise CharacterSessionError('SESSION_CORRUPT')
                message_ids.add(m['message_id'])
                messages[m['message_id']] = m
                if m['speaker_instance_id'] not in participant_ids or set(m['visibility']['audience_instance_ids']) != participant_ids:
                    raise CharacterSessionError('SESSION_CORRUPT')
                if m['speaker_instance_id'] != (user_id if key == 'user_message' else ai_id):
                    raise CharacterSessionError('SESSION_CORRUPT')
                text(m['content'], 4000 if key == 'user_message' else 8000)
                if m['presentation_mode'] not in {'messenger', 'roleplay'}:
                    raise CharacterSessionError('SESSION_CORRUPT')
            if type(record['committed_revision']) is not int or record['committed_revision'] <= 0:
                raise CharacterSessionError('SESSION_CORRUPT')
            inverse = record['ledger_inverse']
            if set(inverse) != {'added_entry_ids', 'previous_entries'} or not isinstance(inverse['added_entry_ids'], list) or not isinstance(inverse['previous_entries'], list):
                raise CharacterSessionError('SESSION_CORRUPT')
            if len(inverse['added_entry_ids']) > 6 or len(inverse['previous_entries']) > 6:
                raise CharacterSessionError('SESSION_CORRUPT')
            for eid in inverse['added_entry_ids']:
                canonical_id(eid)
            inverses.extend(inverse['previous_entries'])
            validate_notice(record)
        for record in value['turns']:
            turn(record)
        pending_count, attempt_count = 0, 0
        for action in value['requests']:
            canonical_id(action['action_id'])
            if action['action_id'] in action_ids or action['operation'] not in {'send', 'regenerate', 'undo'}:
                raise CharacterSessionError('SESSION_CORRUPT')
            action_ids.add(action['action_id'])
            text(action['fingerprint'], 64)
            if action.get('result_state') not in {None, 'active', 'withdrawn', 'replaced'}:
                raise CharacterSessionError('SESSION_CORRUPT')
            attempts = action['attempts']
            if not isinstance(attempts, list) or not attempts:
                raise CharacterSessionError('SESSION_CORRUPT')
            for attempt in attempts:
                if attempt_contract(attempt) == V3:
                    raise ReplyContractError('v3 requires message-group storage')
                if context_contract(attempt) == C4:
                    raise ContextContractError('C4 requires message-group storage')
                attempt_count += 1
                rid = canonical_id(attempt['request_id'])
                if rid in request_ids or attempt['status'] not in {'pending', 'committed', 'failed', 'cancelled', 'interrupted'}:
                    raise CharacterSessionError('SESSION_CORRUPT')
                request_ids.add(rid)
                if type(attempt['base_revision']) is not int or attempt['base_revision'] < 0:
                    raise CharacterSessionError('SESSION_CORRUPT')
                if attempt['status'] == 'pending':
                    pending_count += 1
                    pending = attempt['pending_input']
                    validate_stored_ooc(pending)
                    if bool(pending.get('ooc_note')) != (context_contract(attempt) == C3):
                        raise CharacterSessionError('SESSION_CORRUPT')
                    text(pending['content'], 4000)
                    canonical_id(pending['user_message_id'])
                    canonical_id(pending['ai_message_id'])
                    if pending['mode'] not in {'messenger', 'roleplay'}:
                        raise CharacterSessionError('SESSION_CORRUPT')
                elif 'pending_input' in attempt:
                    raise CharacterSessionError('SESSION_CORRUPT')
            if 'retry_input' in action:
                retry_input = action['retry_input']
                if validate_contract(retry_input.get('reply_contract_id', 'character.reply.v1')) == V3:
                    raise ReplyContractError('v3 requires message-group storage')
                retry_context = validate_context_contract(retry_input.get('context_contract_id', LEGACY))
                if retry_context == C4:
                    raise ContextContractError('C4 requires message-group storage')
                validate_stored_ooc(retry_input)
                text(retry_input['content'], 4000)
                canonical_id(retry_input['user_message_id'])
                canonical_id(retry_input['ai_message_id'])
                if retry_input['mode'] not in {'messenger', 'roleplay'}:
                    raise CharacterSessionError('SESSION_CORRUPT')
                if bool(retry_input.get('ooc_note')) != (retry_context == C3):
                    raise CharacterSessionError('SESSION_CORRUPT')
                if (retry_context == C3) != (context_contract(attempts[-1]) == C3):
                    raise CharacterSessionError('SESSION_CORRUPT')
            if action.get('archived_turn') is not None:
                turn(action['archived_turn'], archived=True)
                if action['archived_turn']['action_id'] != action['action_id']:
                    raise CharacterSessionError('SESSION_CORRUPT')
                if action['archived_turn'].get('memory_notice') and action['operation'] != 'send':
                    raise CharacterSessionError('SESSION_CORRUPT')
        if pending_count > 1:
            raise CharacterSessionError('SESSION_CORRUPT')
        if attempt_count > MAX_ATTEMPTS:
            raise CharacterSessionError('SESSION_LIMIT')
        for record in turn_records.values():
            owner = next((a for a in value['requests'] if a['action_id'] == record['action_id']), None)
            attempt = next((t for t in owner['attempts'] if t['request_id'] == record['request_id']), None) if owner else None
            if attempt is None or bool(record.get('ooc_note')) != (context_contract(attempt) == C3):
                raise CharacterSessionError('SESSION_CORRUPT')
        for record in value['turns']:
            if record['action_id'] not in action_ids or record['request_id'] not in request_ids:
                raise CharacterSessionError('SESSION_CORRUPT')
            owner = next(a for a in value['requests'] if a['action_id'] == record['action_id'])
            attempt = next(t for t in owner['attempts'] if t['request_id'] == record['request_id'])
            if owner.get('result_turn_id') != record['turn_id'] or owner.get('result_state') != 'active' or attempt['status'] != 'committed':
                raise CharacterSessionError('SESSION_CORRUPT')
            if record.get('memory_notice') and owner['operation'] != 'send':
                raise CharacterSessionError('SESSION_CORRUPT')
        active_count = 0
        for index, entry in enumerate([*value['ledger'], *inverses]):
            eid = canonical_id(entry['entry_id'])
            if (index < len(value['ledger']) and eid in entry_ids) or entry['subject_instance_id'] != ai_id:
                raise CharacterSessionError('SESSION_CORRUPT')
            if index < len(value['ledger']):
                entry_ids.add(eid)
            text(entry['content'], 400)
            if entry['status'] not in {'active', 'superseded'} or entry['kind'] not in {'knowledge', 'belief', 'experience', 'intent', 'relationship'}:
                raise CharacterSessionError('SESSION_CORRUPT')
            if entry['status'] == 'active' and index < len(value['ledger']):
                active_count += 1
            audience = entry['visibility']['audience_instance_ids']
            if not isinstance(audience, list) or len(audience) != len(set(audience)) or set(audience) not in ({ai_id}, participant_ids):
                raise CharacterSessionError('SESSION_CORRUPT')
            if entry['kind'] == 'relationship' and entry.get('about_instance_id') != user_id:
                raise CharacterSessionError('SESSION_CORRUPT')
            if entry.get('about_instance_id') is not None and entry['about_instance_id'] not in participant_ids:
                raise CharacterSessionError('SESSION_CORRUPT')
            canonical_id(entry['created_turn_id'])
            if entry['created_turn_id'] not in turn_ids:
                raise CharacterSessionError('SESSION_CORRUPT')
            source = entry['source']
            if set(source) != {'type', 'message_ids', 'evidence'}:
                raise CharacterSessionError('SESSION_CORRUPT')
            if source['type'] not in {'author', 'player_statement', 'dialogue_event', 'model_inference'}:
                raise CharacterSessionError('SESSION_CORRUPT')
            if not isinstance(source['message_ids'], list) or not isinstance(source['evidence'], list):
                raise CharacterSessionError('SESSION_CORRUPT')
            if not (0 if source['type'] == 'author' else 1) <= len(source['message_ids']) <= 2 or len(source['evidence']) > 2:
                raise CharacterSessionError('SESSION_CORRUPT')
            if len(source['message_ids']) != len(set(source['message_ids'])):
                raise CharacterSessionError('SESSION_CORRUPT')
            if source['type'] == 'model_inference' and entry['kind'] not in {'belief', 'intent', 'relationship'}:
                raise CharacterSessionError('SESSION_CORRUPT')
            for mid in source['message_ids']:
                if mid not in messages or not set(audience) <= set(messages[mid]['visibility']['audience_instance_ids']):
                    raise CharacterSessionError('SESSION_CORRUPT')
            for evidence in source['evidence']:
                if set(evidence) != {'message_id', 'quote'} or evidence['message_id'] not in source['message_ids']:
                    raise CharacterSessionError('SESSION_CORRUPT')
                text(evidence['quote'], 240)
                if evidence['quote'] not in messages[evidence['message_id']]['content']:
                    raise CharacterSessionError('SESSION_CORRUPT')
            if 'memory_annotation' in entry:
                validate_annotation(entry['memory_annotation'], entry, user_id)
                origin = turn_records[entry['created_turn_id']]
                owner = next(a for a in value['requests'] if a['action_id'] == origin['action_id'])
                origin_attempt = next(a for a in owner['attempts'] if a['request_id'] == origin['request_id'])
                if attempt_contract(origin_attempt) != V2 or not entry['source']['message_ids'] or not entry['source']['evidence']:
                    raise CharacterSessionError('SESSION_CORRUPT')
                if entry['source']['type'] == 'player_statement' and any(messages[mid]['speaker_instance_id'] != user_id for mid in entry['source']['message_ids']):
                    raise CharacterSessionError('SESSION_CORRUPT')
                if entry['source']['type'] == 'dialogue_event' and any(messages[mid]['turn_id'] != entry['created_turn_id'] for mid in entry['source']['message_ids']):
                    raise CharacterSessionError('SESSION_CORRUPT')
        if active_count > MAX_ACTIVE:
            raise CharacterSessionError('SESSION_LIMIT')
        by_id = {e['entry_id']: e for e in value['ledger']}
        for record in value['turns']:
            if record.get('memory_notice'):
                for eid in record['memory_notice']['entry_ids']:
                    e = by_id.get(eid)
                    if not e or not e.get('memory_annotation') or e['created_turn_id'] != record['turn_id'] or set(e['visibility']['audience_instance_ids']) != participant_ids or e.get('supersedes_entry_id'):
                        raise CharacterSessionError('SESSION_CORRUPT')
        pending_ids = {p[k] for a in value['requests'] for t in a['attempts']
                       for p in [t.get('pending_input', {})] for k in ('user_message_id', 'ai_message_id') if k in p}
        validate_opening(value.get('opening'), ai_id, value['created_at'],
                         turn_ids | action_ids | request_ids | message_ids | entry_ids | pending_ids | participant_ids)
    except ContextContractError:
        raise CharacterSessionError('CONTEXT_CONTRACT_UNSUPPORTED') from None
    except ReplyContractError:
        raise CharacterSessionError('REPLY_CONTRACT_UNSUPPORTED') from None
    except (KeyError, TypeError, ValueError, AttributeError, StopIteration):
        raise CharacterSessionError('SESSION_CORRUPT') from None


def profile_projection(participant: dict, *, detail=False) -> dict:
    """Never inject external extensions, metadata or player/NPC flags."""
    profile = participant["profile_snapshot"]
    if participant.get('profile_semantics') == ROLE_SEMANTICS:
        try:
            return structured_projection(profile.get('role_fields'), profile.get('name', ''), detail=detail)
        except CharacterProfileError:
            raise CharacterSessionError('ROLE_FIELDS_INVALID') from None
    if participant.get('profile_semantics', 'legacy') != 'legacy':
        raise CharacterSessionError('SCHEMA_READ_ONLY')
    return {key: profile.get(key, "") for key in ("name", "description", "starting_scene")}
