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
from core.character_chat.service import CharacterChatService, action_by_id, action_view, session_view, session_summary, visible_turn
from core.character_chat.cognition import public_index
from core.worldbook import normalize_worldbook
from utils.asset_catalog import resolve_asset_path
from utils.runtime_paths import PATHS

router = APIRouter(prefix='/api/v1/character-sessions', tags=['character'])
repository = CharacterSessionRepository(PATHS.data_dir / 'character_sessions')
service = CharacterChatService(repository)


@router.get('/{sid}/capacity')
async def capacity(sid: str, request: Request):
    try:
        if request.query_params or await request.body():
            raise CharacterSessionError('INVALID_REQUEST')
        return JSONResponse(capacity_report(repository.load(canonical_id(sid))), headers={'Cache-Control': 'no-store'})
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
        payload = await body(request, {'client_creation_id', 'title', 'ai_asset_ref', 'user_asset_ref', 'world_asset_ref', 'presentation_mode', 'opening_text'},
                             {'client_creation_id', 'ai_asset_ref', 'presentation_mode'})
        creation = canonical_id(payload['client_creation_id'])
        sid = str(uuid5(CREATION_NAMESPACE, creation))
        try:
            opening = normalize_opening(payload.get('opening_text', ''))
        except ValueError:
            raise CharacterSessionError('INVALID_REQUEST') from None
        identity = {k: payload.get(k) for k in ('title', 'ai_asset_ref', 'user_asset_ref', 'world_asset_ref', 'presentation_mode')}
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
            if existing.get('schema_version') != 1:
                raise CharacterSessionError('SCHEMA_READ_ONLY')
            if existing['creation_fingerprint'] != fingerprint:
                raise CharacterSessionError('IDEMPOTENCY_MISMATCH')
            return JSONResponse(session_view(existing), status_code=201)
        ai = load_asset(payload['ai_asset_ref'])
        user = load_asset(payload['user_asset_ref']) if payload.get('user_asset_ref') else None
        value = create_session(creation, ai, payload['ai_asset_ref'], user_profile=user,
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
async def list_sessions(limit: int = 50, cursor: str | None = None, view: str = 'detail'):
    try:
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
                items.append(session_summary(stored) if view == 'summary' else session_view(stored, detail=False))
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
async def get_session(sid: str):
    try:
        return session_view(repository.load(sid))
    except Exception as exc:
        return error_response(exc)


@router.get('/{sid}/turns')
async def turns(sid: str, before: str | None = None, limit: int = 50):
    try:
        if not 1 <= limit <= 50:
            raise CharacterSessionError('INVALID_REQUEST')
        value = repository.load(sid)
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
async def ledger(sid: str, view: str = 'public'):
    try:
        if view not in {'public', 'spoiler'}:
            raise CharacterSessionError('INVALID_REQUEST')
        return {'ledger': public_ledger(repository.load(sid), spoiler=view == 'spoiler'), 'view': view}
    except Exception as exc:
        return error_response(exc)


@router.get('/{sid}/memory/cognition')
async def cognition_index(sid: str, request: Request):
    try:
        if request.query_params or await request.body():
            raise CharacterSessionError('INVALID_REQUEST')
        value = repository.load(sid)
        if value.get('schema_version') != 1:
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
        return service.metadata(sid, payload['expected_revision'], payload.get('title'), payload.get('presentation_mode'), payload.get('preference_settings'))
    except Exception as exc:
        return error_response(exc)


@router.put('/{sid}/memory/important')
async def mark_memory(sid: str, request: Request):
    try:
        payload = await body(request, {'expected_revision', 'entry_id', 'important'}, {'expected_revision', 'entry_id', 'important'})
        return service.memory_mark(sid, payload['expected_revision'], payload['entry_id'], payload['important'])
    except Exception as exc:
        return error_response(exc)


@router.get('/{sid}/memory/{entry_id}/sources')
async def memory_sources(sid: str, entry_id: str):
    try:
        return service.memory_sources(sid, entry_id)
    except Exception as exc:
        return error_response(exc)


@router.put('/{sid}/memory/automatic')
async def enable_automatic_memory(sid: str, request: Request):
    try:
        payload = await body(request, {'expected_revision', 'enabled'}, {'expected_revision', 'enabled'})
        return service.memory_update(sid, payload['expected_revision'], 'enable', payload['enabled'])
    except Exception as exc:
        return error_response(exc)


@router.put('/{sid}/memory/automatic-selection')
async def automatic_memory_selection(sid: str, request: Request):
    try:
        payload = await body(request, {'expected_revision', 'entry_id', 'dismissed'}, {'expected_revision', 'entry_id', 'dismissed'})
        return service.memory_update(sid, payload['expected_revision'], 'selection', payload['entry_id'], payload['dismissed'])
    except Exception as exc:
        return error_response(exc)


@router.post('/{sid}/memory/automatic-selection/release')
async def release_automatic_memory_selection(sid: str, request: Request):
    try:
        payload = await body(request, {'expected_revision', 'root_entry_id'}, {'expected_revision', 'root_entry_id'})
        return service.memory_update(sid, payload['expected_revision'], 'release', payload['root_entry_id'])
    except Exception as exc:
        return error_response(exc)


@router.put('/{sid}/memory/notice-ack')
async def acknowledge_memory_notice(sid: str, request: Request):
    try:
        payload = await body(request, {'expected_revision', 'action_id'}, {'expected_revision', 'action_id'})
        return service.memory_update(sid, payload['expected_revision'], 'acknowledge', payload['action_id'])
    except Exception as exc:
        return error_response(exc)


@router.delete('/{sid}')
async def delete(sid: str, request: Request):
    try:
        payload = await body(request, {'expected_revision'}, {'expected_revision'})
        service._check_blocked(sid)
        repository.delete(sid, expected_revision=payload['expected_revision'])
        return Response(status_code=204)
    except Exception as exc:
        return error_response(exc)


@router.get('/{sid}/actions/{aid}')
async def action_status(sid: str, aid: str, request_id: str | None = None):
    try:
        canonical_id(aid)
        if request_id:
            canonical_id(request_id)
        value = repository.load(sid)
        return action_view(value, action_by_id(value, aid), request_id)
    except Exception as exc:
        return error_response(exc)


@router.post('/{sid}/requests/{rid}/cancel')
async def cancel(sid: str, rid: str):
    try:
        return service.cancel(sid, rid)
    except Exception as exc:
        return error_response(exc)


async def deliver(sid, request, payload, retry_action_id=None):
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
        payload = await body(request, {'client_action_id', 'expected_revision', 'operation', 'content', 'target_turn_id', 'delivery', 'ooc_note'},
                             {'client_action_id', 'expected_revision', 'operation'})
        return await deliver(sid, request, payload)
    except Exception as exc:
        return error_response(exc)


@router.post('/{sid}/actions/{aid}/retry')
async def retry(sid: str, aid: str, request: Request):
    try:
        payload = await body(request, {'expected_revision', 'retry_of', 'retry_token', 'delivery'},
                             {'expected_revision', 'retry_of', 'retry_token'})
        return await deliver(sid, request, payload, retry_action_id=aid)
    except Exception as exc:
        return error_response(exc)
