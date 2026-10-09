"""Safe HTTP projections and fetch-POST SSE for independent character sessions."""
import asyncio
import hashlib
import json
import os
import time
from uuid import uuid5

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from core.character_chat.models import (CharacterSessionError, CREATION_NAMESPACE, MAX_SNAPSHOT_BYTES,
                                        canonical_id, create_session, json_bytes, text, validate_depth)
from core.character_chat.contract import public_ledger, unique_object
from core.character_chat.opening import normalize_opening
from core.character_chat.capacity import capacity_report
from core.character_chat.errors import ERROR_STATUS, message, retryable
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat.service import CharacterChatService, action_by_id, action_view as legacy_action_view, session_view as legacy_session_view, session_summary as legacy_session_summary, visible_turn
from core.character_chat import group_views
from core.character_chat.capacity import group_capacity_report
from core.character_chat.group_creation import create_group_session
from core.character_chat.runtime import validate_supported_session
from api.v1.character_group_http import GroupSubscription, display_mode
from core.character_chat.cognition import public_index
from core.worldbook import normalize_worldbook
from utils.asset_catalog import resolve_asset_path
from utils.runtime_paths import PATHS

router = APIRouter(prefix='/api/v1/character-sessions', tags=['character'])
repository = CharacterSessionRepository(PATHS.data_dir / 'character_sessions', validator=validate_supported_session, supported_schemas=(1, 2))
service = CharacterChatService(repository, recover=False)


def request_repository(request):
    runtime = getattr(request.app.state, 'character_runtime', None)
    return runtime.repository if runtime else repository


def load_supported(request, sid):
    selected = request_repository(request)
    value = selected.load(sid)
    if value.get('schema_version') not in selected.supported_schemas:
        raise CharacterSessionError('SCHEMA_READ_ONLY')
    return value


def legacy_service(request):
    runtime = getattr(request.app.state, 'character_runtime', None)
    return runtime.legacy if runtime else service


def group_service(request):
    runtime = getattr(request.app.state, 'character_runtime', None)
    if runtime is None:
        raise CharacterSessionError('SERVICE_UNAVAILABLE')
    return runtime.require_groups()


def session_service(request, sid):
    repository = request_repository(request)
    value = repository.load(sid)
    if value.get('schema_version') == 2:
        if 2 not in repository.supported_schemas:
            raise CharacterSessionError('SCHEMA_READ_ONLY')
        return group_service(request)
    if value.get('schema_version') != 1:
        raise CharacterSessionError('SCHEMA_READ_ONLY')
    return legacy_service(request)


def session_view(value, *, detail=True):
    return group_views.public_session(value, detail=detail) if value.get('schema_version') == 2 else legacy_session_view(value, detail=detail)


def session_summary(value):
    return group_views.session_summary(value) if value.get('schema_version') == 2 else legacy_session_summary(value)


def action_view(value, action, request_id=None):
    return (group_views.action_view if value.get('schema_version') == 2 else legacy_action_view)(value, action, request_id)


def proactive_service(request):
    runtime = getattr(request.app.state, 'character_runtime', None)
    if runtime is None:
        raise CharacterSessionError('SERVICE_UNAVAILABLE')
    return runtime.require_proactive()


@router.get('/contact-quota')
async def contact_quota(request: Request):
    try:
        return JSONResponse(proactive_service(request).quota_settings(), headers={'Cache-Control': 'no-store'})
    except Exception as exc:
        return error_response(exc)


@router.put('/contact-batch')
async def update_contact_batch(request: Request):
    try:
        payload = await body(request, {'targets', 'enabled'}, {'targets', 'enabled'})
        return proactive_service(request).configure_batch(payload)
    except Exception as exc:
        return error_response(exc)


@router.put('/contact-quota')
async def update_contact_quota(request: Request):
    try:
        payload = await body(request, {'call_limit', 'contact_limit'}, set())
        return proactive_service(request).quota_settings(payload)
    except Exception as exc:
        return error_response(exc)


@router.get('/{sid}/proactive')
async def contact_settings(sid: str, request: Request):
    try:
        load_supported(request, sid)
        return JSONResponse(proactive_service(request).view(sid), headers={'Cache-Control': 'no-store'})
    except Exception as exc:
        return error_response(exc)


@router.put('/{sid}/proactive')
async def update_contact_settings(sid: str, request: Request):
    try:
        payload = await body(request, {'expected_revision', 'settings'}, {'expected_revision', 'settings'})
        if not isinstance(payload['settings'], dict):
            raise CharacterSessionError('INVALID_REQUEST')
        return proactive_service(request).configure(sid, {**payload['settings'], 'expected_revision': payload['expected_revision']})
    except Exception as exc:
        return error_response(exc)


@router.post('/{sid}/activity')
async def contact_activity(sid: str, request: Request):
    try:
        payload = await body(request, {'client_id'}, {'client_id'})
        return proactive_service(request).activity(sid, payload['client_id'])
    except Exception as exc:
        return error_response(exc)


@router.get('/{sid}/capacity')
async def capacity(sid: str, request: Request):
    try:
        if request.query_params or await request.body():
            raise CharacterSessionError('INVALID_REQUEST')
        repository = request_repository(request)
        value = repository.load(canonical_id(sid))
        if value.get('schema_version') not in repository.supported_schemas:
            raise CharacterSessionError('SCHEMA_READ_ONLY')
        report = group_capacity_report(value) if value.get('schema_version') == 2 else capacity_report(value)
        return JSONResponse(report, headers={'Cache-Control': 'no-store'})
    except CharacterSessionError as exc:
        return error_response(exc)

def error_response(exc, **identity):
    code = getattr(exc, 'code', 'SESSION_CORRUPT')
    return JSONResponse({'error': {'code': code, 'message': message(code), 'retryable': retryable(code)},
                         **identity}, status_code=ERROR_STATUS.get(code, 500))


async def body(request, allowed, required=()):
    raw = await request.body()
    if len(raw) > 65536:
        raise CharacterSessionError('INPUT_LIMIT')
    try:
        value = json.loads(raw, object_pairs_hook=unique_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        validate_depth(value, 12)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise CharacterSessionError('INVALID_REQUEST') from None
    if not isinstance(value, dict) or not set(value) <= set(allowed) or not set(required) <= set(value):
        raise CharacterSessionError('INVALID_REQUEST')
    if 'expected_revision' in value and (type(value['expected_revision']) is not int or value['expected_revision'] < 0):
        raise CharacterSessionError('INVALID_REQUEST')
    return value


def load_asset(ref, *, world=False):
    if not isinstance(ref, dict) or set(ref) != {'kind', 'key'} or ref.get('kind') != ('worldbook' if world else 'character'):
        raise CharacterSessionError('INVALID_REQUEST')
    key = text(ref.get('key'), 1024)
    path = resolve_asset_path('worldbooks' if world else 'characters', key)
    if not path or path.is_symlink():
        raise CharacterSessionError('INVALID_REQUEST')
    try:
        with path.open('rb') as handle:
            raw = handle.read(MAX_SNAPSHOT_BYTES + 1)
        if len(raw) > MAX_SNAPSHOT_BYTES:
            raise CharacterSessionError('INPUT_LIMIT')
        asset = yaml.safe_load(raw)
        if not isinstance(asset, dict):
            raise CharacterSessionError('INVALID_REQUEST')
        return normalize_worldbook(asset) if world else asset
    except (OSError, yaml.YAMLError):
        raise CharacterSessionError('INVALID_REQUEST') from None


@router.post('')
@router.post('/')
async def create(request: Request):
    try:
        repository = request_repository(request)
        payload = await body(request, {'client_creation_id', 'title', 'ai_asset_ref', 'user_asset_ref', 'world_asset_ref', 'presentation_mode', 'opening_text', 'schema_version'},
                             {'client_creation_id', 'ai_asset_ref', 'presentation_mode'})
        version = payload.get('schema_version', 1)
        if type(version) is not int or version not in (1, 2):
            raise CharacterSessionError('INVALID_REQUEST')
        if version == 2:
            group_service(request)
        creation = canonical_id(payload['client_creation_id'])
        sid = str(uuid5(CREATION_NAMESPACE, creation))
        try:
            opening = normalize_opening(payload.get('opening_text', ''))
        except ValueError:
            raise CharacterSessionError('INVALID_REQUEST') from None
        identity = {k: payload.get(k) for k in ('title', 'ai_asset_ref', 'user_asset_ref', 'world_asset_ref', 'presentation_mode')}
        if version == 2:
            identity['schema_version'] = 2
        if opening:
            identity['opening_text'] = opening
        fingerprint = hashlib.sha256(json_bytes(identity)).hexdigest()
        # Check tombstone/idempotency before resolving any mutable source asset.
        try:
            existing = repository.load(sid)
        except CharacterSessionError as exc:
            if exc.code != 'SESSION_NOT_FOUND':
                raise
        else:
            if existing.get('schema_version') not in repository.supported_schemas:
                raise CharacterSessionError('SCHEMA_READ_ONLY')
            if existing['schema_version'] != version or existing['creation_fingerprint'] != fingerprint:
                raise CharacterSessionError('IDEMPOTENCY_MISMATCH')
            return JSONResponse(session_view(existing), status_code=201)
        ai = load_asset(payload['ai_asset_ref'])
        user = load_asset(payload['user_asset_ref']) if payload.get('user_asset_ref') else None
        constructor = create_group_session if version == 2 else create_session
        value = constructor(creation, ai, payload['ai_asset_ref'], user_profile=user,
            user_asset_ref=payload.get('user_asset_ref'), title=payload.get('title'), presentation_mode=payload['presentation_mode'], opening_text=opening)
        value['creation_fingerprint'] = fingerprint
        if payload.get('world_asset_ref'):
            world = load_asset(payload['world_asset_ref'], world=True)
            validate_depth(world, 32)
            if len(json_bytes(world)) > MAX_SNAPSHOT_BYTES:
                raise CharacterSessionError('INPUT_LIMIT')
            value['world_binding'] = {'asset_ref': payload['world_asset_ref'],
                'source_hash': hashlib.sha256(json_bytes(world)).hexdigest(), 'snapshot': world}
        return JSONResponse(session_view(repository.create(value)), status_code=201)
    except Exception as exc:
        return error_response(exc)


@router.get('')
@router.get('/')
async def list_sessions(request: Request, limit: int = 50, cursor: str | None = None, view: str = 'detail'):
    try:
        repository = request_repository(request)
        if not 1 <= limit <= 50 or view not in {'detail', 'summary'}:
            raise CharacterSessionError('INVALID_REQUEST')
        if cursor:
            canonical_id(cursor)
        items = []
        ids = [sid for sid in repository.session_ids() if not cursor or sid > cursor]
        last = None
        for sid in ids:
            last = sid
            try:
                stored = repository.load(sid)
                supported = stored.get('schema_version') in repository.supported_schemas
                summary = session_summary if supported else legacy_session_summary
                detail = session_view if supported else legacy_session_view
                items.append(summary(stored) if view == 'summary' else detail(stored, detail=False))
            except CharacterSessionError as exc:
                if exc.code == 'SESSION_DELETED':
                    continue
                fallback = {'session_id': sid, 'title': '无法读取的对话', 'revision': 0,
                            'pending': None, 'read_error': exc.code}
                if view != 'summary':
                    fallback['participants'] = []
                items.append(fallback)
            if len(items) == limit:
                break
        return {'sessions': items, 'next_cursor': last if last and any(sid > last for sid in ids) else None}
    except Exception as exc:
        return error_response(exc)


@router.get('/{sid}')
async def get_session(sid: str, request: Request):
    try:
        repository = request_repository(request)
        value = repository.load(sid)
        projection = session_view if value.get('schema_version') in repository.supported_schemas else legacy_session_view
        return projection(value)
    except Exception as exc:
        return error_response(exc)


@router.get('/{sid}/turns')
async def turns(sid: str, request: Request, before: str | None = None, limit: int = 50):
    try:
        if not 1 <= limit <= 50:
            raise CharacterSessionError('INVALID_REQUEST')
        value = request_repository(request).load(sid)
        if value.get('schema_version') != 1:
            raise CharacterSessionError('SCHEMA_READ_ONLY')
        items = value['turns']
        if before:
            canonical_id(before)
            index = next((i for i, t in enumerate(items) if t['turn_id'] == before), None)
            if index is None:
                raise CharacterSessionError('INVALID_REQUEST')
            items = items[:index]
        page = items[-limit:]
        return {'turns': [visible_turn(t) for t in page], 'next_cursor': page[0]['turn_id'] if len(items) > limit else None}
    except Exception as exc:
        return error_response(exc)


@router.get('/{sid}/ledger')
async def ledger(sid: str, request: Request, view: str = 'public'):
    try:
        if view not in {'public', 'spoiler'}:
            raise CharacterSessionError('INVALID_REQUEST')
        return {'ledger': public_ledger(request_repository(request).load(sid), spoiler=view == 'spoiler'), 'view': view}
    except Exception as exc:
        return error_response(exc)


@router.get('/{sid}/memory/cognition')
async def cognition_index(sid: str, request: Request):
    try:
        if request.query_params or await request.body():
            raise CharacterSessionError('INVALID_REQUEST')
        repository = request_repository(request)
        value = repository.load(sid)
        if value.get('schema_version') not in repository.supported_schemas:
            raise CharacterSessionError('SCHEMA_READ_ONLY')
        return JSONResponse(public_index(value), headers={'Cache-Control': 'no-store'})
    except Exception as exc:
        response = error_response(exc)
        response.headers['Cache-Control'] = 'no-store'
        return response


@router.patch('/{sid}')
async def patch(sid: str, request: Request):
    try:
        payload = await body(request, {'expected_revision', 'title', 'presentation_mode', 'preference_settings'}, {'expected_revision'})
        if 'preference_settings' in payload and not isinstance(payload['preference_settings'], dict):
            raise CharacterSessionError('INVALID_REQUEST')
        return session_service(request, sid).metadata(sid, payload['expected_revision'], payload.get('title'), payload.get('presentation_mode'), payload.get('preference_settings'))
    except Exception as exc:
        return error_response(exc)


@router.put('/{sid}/memory/important')
async def mark_memory(sid: str, request: Request):
    try:
        payload = await body(request, {'expected_revision', 'entry_id', 'important'}, {'expected_revision', 'entry_id', 'important'})
        return session_service(request, sid).memory_mark(sid, payload['expected_revision'], payload['entry_id'], payload['important'])
    except Exception as exc:
        return error_response(exc)


@router.get('/{sid}/memory/{entry_id}/sources')
async def memory_sources(sid: str, entry_id: str, request: Request):
    try:
        return session_service(request, sid).memory_sources(sid, entry_id)
    except Exception as exc:
        return error_response(exc)


@router.put('/{sid}/memory/automatic')
async def enable_automatic_memory(sid: str, request: Request):
    try:
        payload = await body(request, {'expected_revision', 'enabled'}, {'expected_revision', 'enabled'})
        return session_service(request, sid).memory_update(sid, payload['expected_revision'], 'enable', payload['enabled'])
    except Exception as exc:
        return error_response(exc)


@router.put('/{sid}/memory/automatic-selection')
async def automatic_memory_selection(sid: str, request: Request):
    try:
        payload = await body(request, {'expected_revision', 'entry_id', 'dismissed'}, {'expected_revision', 'entry_id', 'dismissed'})
        return session_service(request, sid).memory_update(sid, payload['expected_revision'], 'selection', payload['entry_id'], payload['dismissed'])
    except Exception as exc:
        return error_response(exc)


@router.post('/{sid}/memory/automatic-selection/release')
async def release_automatic_memory_selection(sid: str, request: Request):
    try:
        payload = await body(request, {'expected_revision', 'root_entry_id'}, {'expected_revision', 'root_entry_id'})
        return session_service(request, sid).memory_update(sid, payload['expected_revision'], 'release', payload['root_entry_id'])
    except Exception as exc:
        return error_response(exc)


@router.put('/{sid}/memory/notice-ack')
async def acknowledge_memory_notice(sid: str, request: Request):
    try:
        payload = await body(request, {'expected_revision', 'action_id'}, {'expected_revision', 'action_id'})
        return session_service(request, sid).memory_update(sid, payload['expected_revision'], 'acknowledge', payload['action_id'])
    except Exception as exc:
        return error_response(exc)


@router.delete('/{sid}')
async def delete(sid: str, request: Request):
    try:
        payload = await body(request, {'expected_revision'}, {'expected_revision'})
        try:
            selected = session_service(request, sid)
        except CharacterSessionError as exc:
            if exc.code == 'SESSION_DELETED':
                return Response(status_code=204)
            raise
        (selected._check if hasattr(selected, '_check') else selected._check_blocked)(sid)
        request_repository(request).delete(sid, expected_revision=payload['expected_revision'])
        return Response(status_code=204)
    except Exception as exc:
        return error_response(exc)


@router.get('/{sid}/actions/{aid}')
async def action_status(sid: str, aid: str, request: Request, request_id: str | None = None):
    try:
        canonical_id(aid)
        if request_id:
            canonical_id(request_id)
        value = load_supported(request, sid)
        return action_view(value, action_by_id(value, aid), request_id)
    except Exception as exc:
        return error_response(exc)


@router.post('/{sid}/requests/{rid}/cancel')
async def cancel(sid: str, rid: str, request: Request):
    try:
        return session_service(request, sid).cancel(sid, rid)
    except Exception as exc:
        return error_response(exc)


async def deliver(sid, request, payload, retry_action_id=None):
    service = legacy_service(request)
    if int(os.environ.get('WEB_CONCURRENCY', '1')) > 1:
        raise CharacterSessionError('CONNECTION_UNSUPPORTED')
    result = service.begin(sid, payload, retry_action_id=retry_action_id)
    if 'existing' in result:
        value = result['existing']
        return JSONResponse(value, status_code=202 if value['status'] == 'pending' else 200)
    rid = result['job']['request_id']
    if payload.get('delivery', 'stream') == 'non_stream':
        task = asyncio.create_task(service.execute(rid, lambda *_: None))
        while not task.done():
            if await request.is_disconnected():
                service.cancel(sid, rid, code='CLIENT_DISCONNECTED')
            await asyncio.sleep(0.05)
        value = await task
        if value['status'] == 'failed':
            return error_response(CharacterSessionError(value['error_code']), **value)
        return value
    queue = asyncio.Queue(maxsize=64)
    overflow = False
    def emit(name, data):
        nonlocal overflow
        if overflow:
            return
        try:
            queue.put_nowait((name, data))
        except asyncio.QueueFull:
            overflow = True
            # Bounded consumer backlog cancels instead of accumulating private text.
            service.cancel(sid, rid, code='CLIENT_DISCONNECTED')
    task = asyncio.create_task(service.execute(rid, emit))
    async def events():
        heartbeat = time.monotonic()
        try:
            while not (task.done() and queue.empty()):
                if overflow or await request.is_disconnected():
                    service.cancel(sid, rid, code='CLIENT_DISCONNECTED')
                    break
                try:
                    name, data = await asyncio.wait_for(queue.get(), 0.2)
                except TimeoutError:
                    if time.monotonic() - heartbeat >= 15:
                        yield ': keepalive\n\n'
                        heartbeat = time.monotonic()
                    continue
                yield 'event: ' + name + '\ndata: ' + json.dumps(data, ensure_ascii=False) + '\n\n'
        finally:
            if not task.done():
                service.cancel(sid, rid, code='CLIENT_DISCONNECTED')
            await task
    return StreamingResponse(events(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@router.post('/{sid}/actions')
async def action(sid: str, request: Request):
    try:
        if load_supported(request, sid).get('schema_version') == 2:
            payload = await body(request, {'client_action_id', 'expected_revision', 'operation', 'content', 'target_group_id', 'delivery', 'display_mode', 'ooc_note'},
                                 {'client_action_id', 'expected_revision', 'operation'})
            selected = group_service(request)
            mode = display_mode(payload)
            operation = payload.pop('operation')
            payload.pop('delivery', None); payload.pop('display_mode', None)
            if operation == 'send':
                record = await selected.send(sid, payload, mode)
            elif operation in ('undo', 'regenerate'):
                record = await selected.batch(sid, {**payload, 'operation': operation}, mode)
            else:
                raise CharacterSessionError('INVALID_REQUEST')
            value = request_repository(request).load(sid)
            return group_action_response(value, record['action_id'])
        payload = await body(request, {'client_action_id', 'expected_revision', 'operation', 'content', 'target_turn_id', 'delivery', 'ooc_note'},
                             {'client_action_id', 'expected_revision', 'operation'})
        return await deliver(sid, request, payload)
    except Exception as exc:
        return error_response(exc)


@router.post('/{sid}/actions/{aid}/retry')
async def retry(sid: str, aid: str, request: Request):
    try:
        if load_supported(request, sid).get('schema_version') == 2:
            payload = await body(request, {'expected_revision', 'retry_of', 'retry_token', 'delivery', 'display_mode'},
                                 {'expected_revision', 'retry_of', 'retry_token'})
            mode = display_mode(payload)
            payload.pop('delivery', None); payload.pop('display_mode', None)
            result = await group_service(request).retry(sid, aid, payload, mode)
            return group_action_response(request_repository(request).load(sid), aid, result['request_id'])
        payload = await body(request, {'expected_revision', 'retry_of', 'retry_token', 'delivery'},
                             {'expected_revision', 'retry_of', 'retry_token'})
        return await deliver(sid, request, payload, retry_action_id=aid)
    except Exception as exc:
        return error_response(exc)


def group_action_response(value, aid, request_id=None):
    result = action_view(value, action_by_id(value, aid), request_id)
    pending = result['status'] in ('queued', 'pending') or result.get('group_status') == 'delivering'
    return JSONResponse(result, status_code=202 if pending else 200, headers={'Cache-Control': 'no-store'})


@router.get('/{sid}/groups')
async def groups(sid: str, request: Request, before: str | None = None, limit: int = 20):
    try:
        value = load_supported(request, sid)
        if value.get('schema_version') != 2:
            raise CharacterSessionError('SCHEMA_READ_ONLY')
        if set(request.query_params) - {'before', 'limit'} or await request.body():
            raise CharacterSessionError('INVALID_REQUEST')
        return JSONResponse(group_views.group_page(value, before, limit), headers={'Cache-Control': 'no-store'})
    except Exception as exc:
        return error_response(exc)


@router.put('/{sid}/read')
async def read_messages(sid: str, request: Request):
    try:
        value = load_supported(request, sid)
        if value.get('schema_version') != 2:
            raise CharacterSessionError('SCHEMA_READ_ONLY')
        payload = await body(request, {'seq'}, {'seq'})
        seq = payload['seq']
        if type(seq) is not int or not 0 <= seq <= 9007199254740991:
            raise CharacterSessionError('INVALID_REQUEST')
        state = group_service(request).read(sid, seq)
        return {k: state[k] for k in ('session_id', 'revision', 'read_ai_seq', 'unread_count')}
    except Exception as exc:
        return error_response(exc)


@router.get('/{sid}/events')
async def subscribe(sid: str, request: Request):
    try:
        if request.query_params or await request.body():
            raise CharacterSessionError('INVALID_REQUEST')
        value = load_supported(request, sid)
        if value.get('schema_version') != 2:
            raise CharacterSessionError('SCHEMA_READ_ONLY')
        return GroupSubscription(group_service(request), sid).response(request)
    except Exception as exc:
        return error_response(exc)
