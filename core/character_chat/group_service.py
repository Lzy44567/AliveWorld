"""Server-owned C4 workers. Disconnected subscribers do not own generation."""
import asyncio
import copy
from datetime import datetime, timezone

from .models import CharacterSessionError, canonical_id
from .transport import CharacterTransport
from .preferences import load_preferences, session_settings
from .group_context import build_group_context
from .group_lifecycle import (accept_input, claim_inputs, busy, current_attempt, commit_generated, check_revision,
                              deliver, fail_generation, recover_groups, mark_read, batch_action, retry_group)
from .group_records import conversation_projection, unread_messages, pending_inputs, active_groups
from .contract import public_ledger
from .errors import ERROR_MESSAGES


def public_group(group):
    keys = ('group_id', 'action_id', 'request_id', 'input_ids', 'status', 'display_mode',
            'mode_at_generation', 'delivered_count', 'created_at', 'committed_revision', 'error_code')
    value = {k: copy.deepcopy(group[k]) for k in keys if k in group}
    value['bubbles'] = copy.deepcopy(group['bubbles'][:group['delivered_count']])
    return value


def public_session(session):
    group = busy(session)
    groups = [g for g in active_groups(session) if g['status'] in {'complete', 'partial_failed', 'delivering', 'generating'}][-20:]
    ids = {mid for g in groups for mid in g['input_ids']} | {
        b['message']['message_id'] for g in groups for b in g['bubbles'][:g['delivered_count']]}
    ids |= {i['input_id'] for i in pending_inputs(session)}
    return {'session_id': session['session_id'], 'revision': session['revision'],
            'messages': [row for row in conversation_projection(session) if row['message']['message_id'] in ids],
            'ledger': public_ledger(session),
            'read_ai_seq': session['read_ai_seq'], 'unread_count': len(unread_messages(session)),
            'queued_count': len(pending_inputs(session)), 'busy_group': public_group(group) if group else None}


class CharacterGroupService:
    """Opt-in schema2 service; the live schema1 service is not switched here.

    All public methods run on one application event loop. Repository mutations
    stay synchronous and short; no lock spans a provider call or display wait.
    """
    def __init__(self, repository, transport=None, *, preference_loader=None, slots=None):
        self.repository = repository
        self.transport = transport or CharacterTransport()
        self.preference_loader = preference_loader or load_preferences
        self.slots = slots or asyncio.Semaphore(4)
        self.workers = {}
        self.subscribers = {}
        self.event_sequences = {}
        self.display_modes = {}
        self.wake_pending = {}
        self.resuming = set()
        self.resume_continue = set()
        self.blocked = set()
        self.closed = False
        self.started = False

    def _transaction(self, sid, mutation):
        def change(value):
            if value.get('schema_version') != 2:
                raise CharacterSessionError('SCHEMA_READ_ONLY')
            before = copy.deepcopy(value)
            result = mutation(value)
            return result, value != before
        return self.repository.transaction(sid, change)

    def _check(self, sid):
        canonical_id(sid)
        if self.closed:
            raise CharacterSessionError('SERVICE_CLOSED')
        if sid in self.blocked:
            raise CharacterSessionError('PERSISTENCE_FAILED')

    def subscribe(self, sid, callback):
        self._check(sid)
        self.subscribers.setdefault(sid, set()).add(callback)
        def detach():
            self.subscribers.get(sid, set()).discard(callback)
        return detach

    def _publish(self, sid, name, attempt=None, **data):
        rid = attempt['request_id'] if attempt else None
        seq = self.event_sequences.get(rid, 0) + 1
        self.event_sequences[rid] = seq
        body = {'v': 1, 'session_id': sid, 'request_id': rid, 'seq': seq, **data}
        if attempt:
            body['group_id'] = attempt['group_id']
        for callback in tuple(self.subscribers.get(sid, ())):
            try:
                callback(name, copy.deepcopy(body))
            except Exception:
                # A closed/slow UI cannot turn a saved conversation into failure.
                self.subscribers.get(sid, set()).discard(callback)

    def _wake(self, sid, *, explicit=False, resume_only=False):
        task = self.workers.get(sid)
        if task is None or task.done():
            if resume_only:
                self.resuming.add(sid)
            self.workers[sid] = asyncio.create_task(self._run(sid, explicit=explicit, resume_only=resume_only))
        elif task.cancelling():
            # Cancel -> immediate retry/send must survive the old worker's
            # finally block. Ordinary input while generating is not a retry.
            self.wake_pending[sid] = self.wake_pending.get(sid, False) or explicit
        elif explicit and sid in self.resuming:
            self.resume_continue.add(sid)

    async def start(self):
        if self.started or self.closed:
            return
        self.started = True
        for sid in self.repository.session_ids():
            try:
                self._transaction(sid, recover_groups)
                group = busy(self.repository.load(sid))
                if group and group['status'] == 'delivering':
                    self._wake(sid, resume_only=True)
            except (CharacterSessionError, KeyError, TypeError):
                continue

    async def close(self):
        self.closed = True
        tasks = list(self.workers.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.subscribers.clear()

    def view(self, sid):
        self._check(sid)
        value = self.repository.load(sid)
        if value.get('schema_version') != 2:
            raise CharacterSessionError('SCHEMA_READ_ONLY')
        return public_session(value)

    def _event_state(self, sid):
        value = self.view(sid)
        # Full history/ledger stays in the authoritative GET response, not in
        # every stream frame. Candidate text is never a public state field.
        return {k: value[k] for k in ('session_id', 'revision', 'read_ai_seq', 'unread_count', 'queued_count')}

    async def send(self, sid, payload, display_mode='stream'):
        self._check(sid)
        self.set_display(sid, display_mode)
        action, changed = self._transaction(sid, lambda s: accept_input(s, payload))
        if changed:
            self._publish(sid, 'input_saved', action_id=action['action_id'], state=self._event_state(sid))
            self._wake(sid, explicit=True)
        return action

    def set_display(self, sid, mode):
        self._check(sid)
        if mode not in {'stream', 'gaps', 'instant'}:
            raise CharacterSessionError('INVALID_REQUEST')
        self.display_modes[sid] = mode

    def read(self, sid, seq):
        self._check(sid)
        changed = self._transaction(sid, lambda s: mark_read(s, seq))
        return {'changed': changed, **self.view(sid)}

    async def batch(self, sid, payload, display_mode='stream'):
        self._check(sid)
        self.set_display(sid, display_mode)
        result, changed = self._transaction(sid, lambda s: batch_action(s, payload, display_mode))
        if changed:
            self._publish(sid, 'state_changed', state=self._event_state(sid))
            if payload['operation'] == 'regenerate':
                self._wake(sid)
        return result

    async def retry(self, sid, action_id, payload, display_mode='stream'):
        self._check(sid)
        self.set_display(sid, display_mode)
        canonical_id(action_id)
        if not isinstance(payload, dict) or set(payload) != {'expected_revision', 'retry_of', 'retry_token'}:
            raise CharacterSessionError('INVALID_REQUEST')
        canonical_id(payload['retry_of']); canonical_id(payload['retry_token'])
        def retry(value):
            # Retry-token replay must remain idempotent after a newer revision.
            old = next((a for a in value['requests'] if a['action_id'] == action_id), None)
            replay = old and any(t.get('retry_token') == payload['retry_token'] for t in old['attempts'])
            if not replay:
                check_revision(value, payload['expected_revision'])
            return retry_group(value, action_id, payload['retry_of'], payload['retry_token'], display_mode)
        result, changed = self._transaction(sid, retry)
        if changed:
            self._wake(sid)
        return result

    def cancel(self, sid, rid):
        self._check(sid)
        canonical_id(rid)
        changed = self._transaction(sid, lambda s: fail_generation(s, rid, 'cancelled', 'USER_CANCELLED'))
        if changed:
            attempt = current_attempt(self.repository.load(sid), rid)[1]
            self._publish(sid, 'cancelled', attempt, code='USER_CANCELLED', state=self._event_state(sid))
            task = self.workers.get(sid)
            if task:
                task.cancel()
        return {'cancelled': changed, **self.view(sid)}

    async def wait_idle(self, sid):
        while (task := self.workers.get(sid)) is not None:
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                if asyncio.current_task().cancelling():
                    raise
            if self.workers.get(sid) is task:
                return

    def _terminal(self, sid, attempt, status, code):
        try:
            changed = self._transaction(sid, lambda s: fail_generation(s, attempt['request_id'], status, code))
            if changed:
                self._publish(sid, status, attempt, code=code, state=self._event_state(sid))
        except CharacterSessionError:
            self.blocked.add(sid)
            self._publish(sid, 'failed', attempt, code='PERSISTENCE_FAILED')

    async def _generate(self, sid, attempt):
        try:
            snapshot = self.repository.load(sid)
            config = self.transport.snapshot()
            settings = session_settings(snapshot)
            preferences = self.preference_loader(settings) if settings['enabled'] else []
            plan, messages, entries, report = build_group_context(snapshot, attempt['request_id'], config, preferences=preferences)
            self._publish(sid, 'accepted', attempt, display_mode=attempt['display_mode'],
                          reserved_ai_ids=attempt['reserved_ai_ids'], base_revision=attempt['base_revision'])
            def preview(body):
                self._publish(sid, body['kind'], attempt, ordinal=body['ordinal'],
                              **({'text': body['text']} if 'text' in body else {}))
            # An accepted-event handler may cancel before the provider starts.
            # Do not rely only on task cancellation at the next await boundary.
            authoritative = self.repository.load(sid)
            current = current_attempt(authoritative, attempt['request_id'])[1]
            if current['status'] != 'pending' or current['context_epoch'] != authoritative['context_epoch']:
                return False
            raw = await self.transport.generate(config, plan, report,
                                                'stream' if attempt['display_mode'] == 'stream' else 'non_stream', preview)
            self._publish(sid, 'validating', attempt)
            group = self._transaction(sid, lambda s: commit_generated(s, attempt['request_id'], raw, messages, entries))
            self._publish(sid, 'group_saved', attempt, group=public_group(group), state=self._event_state(sid))
            return True
        except asyncio.CancelledError:
            status, code = ('interrupted', 'PROCESS_INTERRUPTED') if self.closed else ('cancelled', 'USER_CANCELLED')
            self._terminal(sid, attempt, status, code)
            raise
        except Exception as exc:
            code = getattr(exc, 'code', 'PROVIDER_FAILED')
            if code not in ERROR_MESSAGES and code != 'PERSISTENCE_FAILED':
                code = 'PROVIDER_FAILED'
            self._terminal(sid, attempt, 'failed', code)
            return False

    async def _run(self, sid, *, explicit=False, resume_only=False):
        try:
            while not self.closed and sid not in self.blocked:
                group = busy(self.repository.load(sid))
                if group and group['status'] == 'delivering':
                    delay = max(0, (datetime.fromisoformat(group['next_due_at']) - datetime.now(timezone.utc)).total_seconds())
                    await asyncio.sleep(delay)
                    def dispatch(value):
                        current = busy(value)
                        if current is None or current['group_id'] != group['group_id']:
                            return None
                        if not deliver(value, current, expected_ordinal=group['delivered_count']):
                            return None
                        return public_group(current)
                    try:
                        delivered = self._transaction(sid, dispatch)
                    except CharacterSessionError:
                        self.blocked.add(sid)
                        self._publish(sid, 'failed', code='PERSISTENCE_FAILED')
                        return
                    if delivered:
                        attempt = current_attempt(self.repository.load(sid), group['request_id'])[1]
                        self._publish(sid, 'group_saved', attempt, group=delivered, state=self._event_state(sid))
                    continue
                if resume_only:
                    if sid not in self.resume_continue:
                        return
                    self.resume_continue.discard(sid)
                    self.resuming.discard(sid)
                    resume_only = False
                    explicit = True
                # Reserve the provider slot before claiming queued input. Gaps
                # release it immediately after generation, not after animation.
                async with self.slots:
                    snapshot = self.repository.load(sid)
                    group = busy(snapshot)
                    if group:
                        attempt = current_attempt(snapshot, group['request_id'])[1]
                    else:
                        attempt = self._transaction(sid, lambda s: claim_inputs(s, self.display_modes.get(sid, 'stream'), explicit=explicit))
                    explicit = False
                    if attempt is None:
                        return
                    if not await self._generate(sid, attempt):
                        return
        except asyncio.CancelledError:
            pass
        except CharacterSessionError as exc:
            if exc.code == 'PERSISTENCE_FAILED':
                self.blocked.add(sid)
            self._publish(sid, 'failed', code=exc.code)
        finally:
            if self.workers.get(sid) is asyncio.current_task():
                self.workers.pop(sid, None)
                self.resuming.discard(sid)
                self.resume_continue.discard(sid)
                if sid in self.wake_pending:
                    explicit = self.wake_pending.pop(sid)
                    if not self.closed and sid not in self.blocked:
                        self._wake(sid, explicit=explicit)
