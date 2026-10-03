"""Atomic actions/attempts, isolated pending generations and reversible turns."""
import asyncio
import copy
import hashlib
from threading import BoundedSemaphore, RLock
from uuid import uuid4

from .models import CharacterSessionError, canonical_id, json_bytes, text, profile_projection
from .contract import now, plan_turn, public_ledger, reverse_ledger
from .context import build_context
from .transport import CharacterTransport
from .errors import message, retryable


def pending_attempt(session):
    return next(((a, t) for a in session['requests'] for t in a['attempts'] if t['status'] == 'pending'), None)


def writable(session, revision):
    if type(revision) is not int or revision < 0:
        raise CharacterSessionError('INVALID_REQUEST')
    if session['revision'] != revision:
        raise CharacterSessionError('REVISION_CONFLICT')
    if pending_attempt(session):
        raise CharacterSessionError('SESSION_BUSY')


def action_by_id(session, aid):
    action = next((a for a in session['requests'] if a['action_id'] == aid), None)
    if action is None:
        raise CharacterSessionError('ACTION_NOT_FOUND')
    return action


def archive_last(session, result_state):
    last = session['turns'].pop()
    original = action_by_id(session, last['action_id'])
    if original.get('archived_turn') is not None:
        raise CharacterSessionError('SESSION_CORRUPT')
    original['archived_turn'] = copy.deepcopy(last)
    original['result_state'] = result_state
    reverse_ledger(session, last['ledger_inverse'])
    return last


def action_view(session, action, request_id=None):
    attempt = next((t for t in action['attempts'] if t['request_id'] == request_id), None) if request_id else action['attempts'][-1]
    if attempt is None:
        raise CharacterSessionError('ACTION_NOT_FOUND')
    result = {'session_id': session['session_id'], 'action_id': action['action_id'],
              'request_id': attempt['request_id'], 'status': attempt['status'],
              'revision': session['revision'], 'operation': action['operation'],
              'result_state': action.get('result_state'), 'result_turn_id': action.get('result_turn_id'),
              'base_revision': attempt['base_revision']}
    for key in ('error_code', 'committed_revision'):
        if key in attempt:
            result[key] = attempt[key]
    if attempt['status'] in {'failed', 'cancelled', 'interrupted'} and action.get('retry_input'):
        result['retry_input'] = action['retry_input']['content']
    if action.get('result_state') == 'active':
        turn = next((t for t in session['turns'] if t['turn_id'] == action['result_turn_id']), None)
        if turn:
            result['turn'] = visible_turn(turn)
            result['turn_id'] = turn['turn_id']
            result['ledger'] = public_ledger(session)
    return result


def visible_turn(turn):
    return {k: copy.deepcopy(v) for k, v in turn.items() if k != 'ledger_inverse'}


def session_summary(session):
    """Public, lightweight conversation projection; never includes archived/private data."""
    if session.get('schema_version') != 1:
        return {'session_id': session['session_id'], 'title': '更高版本会话（只读）',
                'schema_read_only': True, 'pending': None}
    pair = pending_attempt(session)
    last = session['turns'][-1] if session['turns'] else None
    ai = next(p for p in session['participants'] if p['controller'] == 'ai')
    result = {k: session[k] for k in ('session_id', 'title', 'revision', 'presentation_mode', 'created_at')}
    result.update(ai_name=ai['display_name'],
                  last_activity_at=last['created_at'] if last else session['created_at'],
                  last_message_preview=' '.join(last['ai_message']['content'].split())[:160] if last else '',
                  latest_ai_message_id=last['ai_message']['message_id'] if last else None,
                  latest_ai_committed_revision=last['committed_revision'] if last else None,
                  pending=None if not pair else {'action_id': pair[0]['action_id'],
                      'request_id': pair[1]['request_id'], 'status': 'pending', 'base_revision': pair[1]['base_revision']})
    return result


def session_view(session, *, detail=True):
    if session.get('schema_version') != 1:
        return {'session_id': session['session_id'], 'revision': session.get('revision', 0),
                'title': '更高版本会话（只读）', 'schema_read_only': True, 'pending': None,
                'participants': [], 'turns': [], 'ledger': []}
    pair = pending_attempt(session)
    pending = None if pair is None else {'action_id': pair[0]['action_id'],
        'request_id': pair[1]['request_id'], 'status': 'pending', 'base_revision': pair[1]['base_revision']}
    value = {k: session[k] for k in ('session_id', 'title', 'revision', 'presentation_mode', 'created_at', 'updated_at')}
    value['pending'] = pending
    value['participants'] = [{k: copy.deepcopy(p[k]) for k in ('instance_id', 'controller', 'display_name')}
                             | {'profile_snapshot': profile_projection(p, detail=True)}
                             for p in session['participants']]
    value['world_binding'] = None if not session.get('world_binding') else {'name': session['world_binding']['snapshot'].get('name', '')}
    if detail:
        value['turns'] = [visible_turn(t) for t in session['turns'][-20:]]
        value['ledger'] = public_ledger(session)
        failures = [a for a in session['requests'] if a['attempts'][-1]['status'] in {'failed', 'cancelled', 'interrupted'}]
        value['last_failed_action'] = action_view(session, failures[-1]) if failures else None
    return value


class CharacterChatService:
    def __init__(self, repository, transport=None, *, recover=True):
        self.repository = repository
        self.transport = transport or CharacterTransport()
        self.slots = BoundedSemaphore(4)
        self.jobs = {}
        self.tasks = {}
        self.blocked = set()
        self.lock = RLock()
        if recover:
            self.recover_pending()

    def recover_pending(self):
        """Startup-only recovery. Never run from GET or while a task is live."""
        for sid in self.repository.session_ids():
            def recover(value):
                changed = False
                for action in value['requests']:
                    for attempt in action['attempts']:
                        if attempt['status'] == 'pending':
                            action['retry_input'] = attempt.pop('pending_input')
                            attempt.update(status='interrupted', error_code='PROCESS_INTERRUPTED', ended_at=now())
                            changed = True
                return None, changed
            try:
                self.repository.transaction(sid, recover)
            except (CharacterSessionError, TypeError, KeyError):
                # Corrupt/future/deleted data remains untouched and readable via safe error paths.
                continue

    def _check_blocked(self, sid):
        if sid in self.blocked:
            raise CharacterSessionError('PERSISTENCE_FAILED')

    def metadata(self, sid, revision, title=None, presentation_mode=None):
        self._check_blocked(sid)
        if title is None and presentation_mode is None:
            raise CharacterSessionError('INVALID_REQUEST')
        if title is not None:
            text(title, 80)
        if presentation_mode is not None and (not isinstance(presentation_mode, str) or presentation_mode not in {'messenger', 'roleplay'}):
            raise CharacterSessionError('INVALID_REQUEST')
        def update(value):
            writable(value, revision)
            if title is not None:
                value['title'] = title
            if presentation_mode is not None:
                value['presentation_mode'] = presentation_mode
            value['revision'] += 1
            return session_view(value), True
        return self.repository.transaction(sid, update)

    def begin(self, sid, payload, *, retry_action_id=None):
        self._check_blocked(sid)
        delivery = payload.get('delivery', 'stream')
        if not isinstance(delivery, str) or delivery not in {'stream', 'non_stream'}:
            raise CharacterSessionError('INVALID_REQUEST')
        aid = canonical_id(retry_action_id or payload.get('client_action_id'))
        retry_token = canonical_id(payload.get('retry_token')) if retry_action_id else None
        if retry_action_id:
            canonical_id(payload.get('retry_of'))
        job = None
        slot = False
        def start(value):
            nonlocal job, slot
            existing = next((a for a in value['requests'] if a['action_id'] == aid), None)
            if retry_action_id:
                if existing is None:
                    raise CharacterSessionError('ACTION_NOT_FOUND')
                token_attempt = next((t for t in existing['attempts'] if t.get('retry_token') == retry_token), None)
                if token_attempt:
                    if token_attempt.get('retry_of') != payload['retry_of']:
                        raise CharacterSessionError('IDEMPOTENCY_MISMATCH')
                    return {'existing': action_view(value, existing, token_attempt['request_id'])}, False
                if existing.get('result_turn_id') or existing['attempts'][-1]['request_id'] != payload['retry_of'] or existing['attempts'][-1]['status'] not in {'failed', 'cancelled', 'interrupted'}:
                    raise CharacterSessionError('STALE_RETRY')
                operation, content, target = existing['operation'], existing['retry_input']['content'], existing.get('target_turn_id')
                mode = existing['retry_input']['mode']
            else:
                operation = payload.get('operation')
                if not isinstance(operation, str) or operation not in {'send', 'regenerate', 'undo'}:
                    raise CharacterSessionError('INVALID_REQUEST')
                mode = existing.get('mode_at_action', value['presentation_mode']) if existing else value['presentation_mode']
                target, content = payload.get('target_turn_id'), payload.get('content')
                if operation == 'send':
                    text(content, 4000)
                    if target is not None:
                        raise CharacterSessionError('INVALID_REQUEST')
                else:
                    canonical_id(target)
                    if content is not None:
                        raise CharacterSessionError('INVALID_REQUEST')
                fingerprint = hashlib.sha256(json_bytes({'operation': operation, 'content': content,
                    'target_turn_id': target, 'mode': mode})).hexdigest()
                if existing:
                    if existing['fingerprint'] != fingerprint:
                        raise CharacterSessionError('IDEMPOTENCY_MISMATCH')
                    return {'existing': action_view(value, existing)}, False
            writable(value, payload.get('expected_revision'))
            if len(value['requests']) >= 2048 or sum(len(a['attempts']) for a in value['requests']) >= 4096:
                raise CharacterSessionError('SESSION_LIMIT')
            if operation in {'regenerate', 'undo'}:
                if not value['turns'] or value['turns'][-1]['turn_id'] != target:
                    raise CharacterSessionError('REVISION_CONFLICT')
                content = value['turns'][-1]['user_message']['content']
            if operation != 'undo' and operation == 'send' and len(value['turns']) >= 512:
                raise CharacterSessionError('SESSION_LIMIT')
            if not existing:
                existing = {'action_id': aid, 'operation': operation, 'fingerprint': fingerprint, 'mode_at_action': mode,
                            'created_at': now(), 'attempts': [], 'result_state': None}
                if target:
                    existing['target_turn_id'] = target
                value['requests'].append(existing)
            attempt = {'request_id': str(uuid4()), 'base_revision': value['revision'], 'status': 'pending', 'created_at': now()}
            if retry_token:
                attempt.update(retry_of=payload['retry_of'], retry_token=retry_token)
            existing['attempts'].append(attempt)
            if operation == 'undo':
                archive_last(value, 'withdrawn')
                value['revision'] += 1
                attempt.update(status='committed', committed_revision=value['revision'], ended_at=now())
                result = action_view(value, existing)
                result['ledger'] = public_ledger(value)
                return {'existing': result}, True
            if not self.slots.acquire(blocking=False):
                raise CharacterSessionError('CAPACITY_LIMIT')
            slot = True
            attempt['pending_input'] = {'content': content, 'mode': mode,
                'user_message_id': str(uuid4()), 'ai_message_id': str(uuid4())}
            existing['retry_input'] = copy.deepcopy(attempt['pending_input'])
            job = {'session': copy.deepcopy(value), 'action_id': aid, 'request_id': attempt['request_id'], 'delivery': delivery}
            return {'job': {'session_id': sid, 'action_id': aid, 'request_id': attempt['request_id'],
                            'base_revision': value['revision'], 'delivery': delivery}}, True
        try:
            result = self.repository.transaction(sid, start)
            if job:
                # Pin settings and composed prompt before returning control to other requests.
                config = self.transport.snapshot()
                snapshot = job['session']
                action = action_by_id(snapshot, aid)
                attempt = action['attempts'][-1]
                if action['operation'] == 'regenerate':
                    archive_last(snapshot, 'replaced')
                plan, messages, entries, report = build_context(snapshot, attempt['pending_input'], config.get('budget_options'))
                job.update(config=config, plan=plan, messages=messages, entries=entries, report=report)
                with self.lock:
                    self.jobs[job['request_id']] = job
            return result
        except Exception as exc:
            if job:
                try:
                    self._terminal(sid, aid, job['request_id'], 'failed', getattr(exc, 'code', 'PROVIDER_FAILED'))
                except CharacterSessionError:
                    pass
            if slot:
                self.slots.release()
            raise

    def _terminal(self, sid, aid, rid, status, code):
        def end(value):
            action = action_by_id(value, aid)
            attempt = next((t for t in action['attempts'] if t['request_id'] == rid), None)
            if attempt is None:
                raise CharacterSessionError('ACTION_NOT_FOUND')
            if attempt['status'] == 'pending':
                action['retry_input'] = attempt.pop('pending_input')
                attempt.update(status=status, error_code=code, ended_at=now())
                return action_view(value, action, rid), True
            return action_view(value, action, rid), False
        try:
            return self.repository.transaction(sid, end)
        except CharacterSessionError as exc:
            if exc.code == 'PERSISTENCE_FAILED':
                self.blocked.add(sid)
            raise

    def cancel(self, sid, rid, *, code='USER_CANCELLED'):
        canonical_id(rid)
        value = self.repository.load(sid)
        pair = next(((a, t) for a in value['requests'] for t in a['attempts'] if t['request_id'] == rid), None)
        if pair is None:
            raise CharacterSessionError('ACTION_NOT_FOUND')
        result = self._terminal(sid, pair[0]['action_id'], rid, 'cancelled', code)
        with self.lock:
            task = self.tasks.get(rid)
        if task and result['status'] == 'cancelled':
            task.get_loop().call_soon_threadsafe(task.cancel)
        if result['status'] == 'committed':
            result['cancel_result'] = 'already_committed'
        return result

    async def execute(self, rid, emit):
        with self.lock:
            job = self.jobs[rid]
            self.tasks[rid] = asyncio.current_task()
        sid, aid = job['session']['session_id'], job['action_id']
        seq = 0
        def event(name, data):
            nonlocal seq
            seq += 1
            emit(name, {'v': 1, 'session_id': sid, 'action_id': aid, 'request_id': rid, 'seq': seq, **data})
        try:
            event('accepted', {'base_revision': job['session']['revision'], 'delivery': job['delivery']})
            # A cancel that won before this coroutine started must still make zero calls.
            authoritative = self.repository.load(sid)
            if action_view(authoritative, action_by_id(authoritative, aid), rid)['status'] != 'pending':
                raise asyncio.CancelledError()
            raw = await self.transport.generate(job['config'], job['plan'], job['report'], job['delivery'],
                                                lambda body: event('reply_delta', {'text': body}))
            event('validating', {})
            def commit(value):
                action = action_by_id(value, aid)
                attempt = next(t for t in action['attempts'] if t['request_id'] == rid)
                if attempt['status'] != 'pending':
                    return action_view(value, action, rid), False
                if attempt['base_revision'] != value['revision']:
                    raise CharacterSessionError('REVISION_CONFLICT')
                if action['operation'] == 'regenerate':
                    if not value['turns'] or value['turns'][-1]['turn_id'] != action['target_turn_id']:
                        raise CharacterSessionError('REVISION_CONFLICT')
                    archive_last(value, 'replaced')
                candidate, turn = plan_turn(value, action, attempt, raw, job['messages'], job['entries'])
                value.clear()
                value.update(candidate)
                action = action_by_id(value, aid)
                attempt = next(t for t in action['attempts'] if t['request_id'] == rid)
                value['revision'] += 1
                action.update(result_state='active', result_turn_id=turn['turn_id'])
                action.pop('retry_input', None)
                attempt.pop('pending_input', None)
                attempt.update(status='committed', committed_revision=value['revision'], ended_at=now())
                return action_view(value, action, rid), True
            result = self.repository.transaction(sid, commit)
            if result['status'] == 'committed':
                event('committed', result)
            else:
                event('cancelled', {'code': result.get('error_code', 'USER_CANCELLED'), 'revision': result['revision']})
            return result
        except asyncio.CancelledError:
            result = self._terminal(sid, aid, rid, 'cancelled', 'USER_CANCELLED')
            event('cancelled', {'code': result.get('error_code', 'USER_CANCELLED'), 'revision': result['revision']})
            return result
        except Exception as exc:
            code = getattr(exc, 'code', 'PROVIDER_FAILED')
            try:
                result = self._terminal(sid, aid, rid, 'failed', code)
            except CharacterSessionError:
                code = 'PERSISTENCE_FAILED'
                result = {'session_id': sid, 'action_id': aid, 'request_id': rid, 'status': 'failed', 'error_code': code,
                          'revision': job['session']['revision']}
            event('failed', {'code': code, 'message': message(code),
                             'retryable': retryable(code), 'revision': result['revision']})
            return result
        finally:
            with self.lock:
                self.jobs.pop(rid, None)
                self.tasks.pop(rid, None)
            self.slots.release()
