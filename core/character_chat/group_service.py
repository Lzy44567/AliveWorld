"""Server-owned C4 workers. Disconnected subscribers do not own generation."""
import asyncio
import copy
from core.generation_control import generation_scope
from datetime import datetime, timezone

from .models import CharacterSessionError, canonical_id
from .transport import CharacterTransport
from .preferences import load_preferences, session_settings
from .group_context import build_group_context
from .group_lifecycle import (accept_input, claim_inputs, busy, current_attempt, commit_generated, check_revision,
                              deliver, fail_generation, recover_groups, mark_read, batch_action, retry_group)
from .errors import ERROR_MESSAGES
from .legacy_context import build_legacy_retry_context, legacy_snapshot
from .legacy_lifecycle import execution_for_request, begin_legacy_retry, commit_legacy
from .group_views import public_group, public_session
from . import group_settings
from .group_requests import retry_values
from .proactive_contact import invalidate


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
        self.event_owners = {}
        self.display_modes = {}
        self.wake_pending = {}
        self.resuming = set()
        self.resume_continue = set()
        self.blocked = set()
        self.closed = False
        self.started = False
        self.proactive = None

    def _refresh_contact(self, sid):
        if self.proactive is not None:
            self.proactive.refresh(sid)

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
            body['group_id'] = (attempt['legacy_execution']['group_id'] if attempt.get('legacy_execution') else attempt['group_id'])
            if rid not in self.event_owners:
                self.event_owners[rid] = execution_for_request(self.repository.load(sid), rid)[0]['action_id']
            body['action_id'] = self.event_owners[rid]
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
        if self.closed:
            return
        self.closed = True
        sessions = list(self.workers)
        tasks = list(self.workers.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        failure = None
        for sid in sessions:
            try:
                def interrupt(value):
                    current = busy(value)
                    if current and current['status'] == 'generating':
                        return fail_generation(value, current['request_id'], 'interrupted', 'PROCESS_INTERRUPTED')
                    return False
                self._transaction(sid, interrupt)
            except CharacterSessionError as exc:
                self.blocked.add(sid)
                failure = failure or exc
        self.subscribers.clear()
        if failure:
            raise failure

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
            self._refresh_contact(sid)
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

    def metadata(self, sid, revision, title=None, presentation_mode=None, preference_settings=None):
        self._check(sid)
        self._transaction(sid, lambda s: group_settings.metadata(s, revision, title, presentation_mode, preference_settings))
        self._refresh_contact(sid)
        return self.view(sid)

    def memory_mark(self, sid, revision, entry_id, important):
        self._check(sid)
        self._transaction(sid, lambda s: group_settings.mark_memory(s, revision, entry_id, important))
        self._refresh_contact(sid)
        return self.view(sid)

    def memory_update(self, sid, revision, operation, *args):
        self._check(sid)
        self._transaction(sid, lambda s: group_settings.update_memory(s, revision, operation, *args))
        if operation != 'acknowledge':
            self._refresh_contact(sid)
        value = self.view(sid)
        return {k: value[k] for k in ('session_id', 'revision', 'memory_settings')}

    def memory_sources(self, sid, entry_id):
        self._check(sid)
        value = self.repository.load(sid)
        if value.get('schema_version') != 2:
            raise CharacterSessionError('SCHEMA_READ_ONLY')
        return group_settings.memory_sources(value, entry_id)

    async def batch(self, sid, payload, display_mode='stream'):
        self._check(sid)
        self.set_display(sid, display_mode)
        result, changed = self._transaction(sid, lambda s: batch_action(s, payload, display_mode))
        if changed:
            self._publish(sid, 'state_changed', state=self._event_state(sid))
            self._refresh_contact(sid)
            if payload['operation'] == 'regenerate':
                self._wake(sid)
        return result

    async def retry(self, sid, action_id, payload, display_mode='stream'):
        self._check(sid)
        self.set_display(sid, display_mode)
        canonical_id(action_id)
        retry_values(payload)
        def retry(value):
            # Retry-token replay must remain idempotent after a newer revision.
            old = next((a for a in value['requests'] if a['action_id'] == action_id), None)
            replay = old and any(t.get('retry_token') == payload['retry_token'] for t in old['attempts'])
            if not replay:
                check_revision(value, payload['expected_revision'])
            target = old and next((t for t in old['attempts'] if t['request_id'] == payload['retry_of']), None)
            handler = begin_legacy_retry if target and target.get('legacy_attempt') else retry_group
            result = handler(value, action_id, payload['retry_of'], payload['retry_token'], display_mode)
            if result[1]:
                invalidate(value)
            return result
        result, changed = self._transaction(sid, retry)
        if changed:
            self._wake(sid)
            self._refresh_contact(sid)
        return result

    def cancel(self, sid, rid):
        self._check(sid)
        canonical_id(rid)
        changed = self._transaction(sid, lambda s: fail_generation(s, rid, 'cancelled', 'USER_CANCELLED'))
        if changed:
            attempt = execution_for_request(self.repository.load(sid), rid)[1]
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
            budget_options = config.get('budget_options')
            settings = session_settings(snapshot)
            preferences = self.preference_loader(settings) if settings['enabled'] else []
            legacy = bool(attempt.get('legacy_execution'))
            if legacy:
                action, _, _ = execution_for_request(snapshot, attempt['request_id'])
                pending, _, _ = legacy_snapshot(action, attempt)
                plan, messages, entries, report = build_legacy_retry_context(snapshot, action, attempt, budget_options, preferences=preferences)
                mode = attempt['legacy_execution']['display_mode']
                reserved = [pending['ai_message_id']]
            else:
                plan, messages, entries, report = build_group_context(snapshot, attempt['request_id'], budget_options, preferences=preferences)
                mode, reserved = attempt['display_mode'], attempt['reserved_ai_ids']
            self._publish(sid, 'accepted', attempt, display_mode=mode,
                          reserved_ai_ids=reserved, base_revision=attempt['base_revision'],
                          context_omissions=[{k: item[k] for k in ('participant_id', 'field')}
                                            for item in report.get('omitted', []) if item.get('field') == 'dialogue_examples'],
                          **{public: report[key] for public, key in (('world_context_report', 'world_context'),
                             ('memory_context_report', 'memory_context'), ('source_recall_report', 'source_recall')) if key in report})
            legacy_started = False
            def preview(body):
                nonlocal legacy_started
                if mode != 'stream':
                    return
                if legacy:
                    if not body:
                        return
                    if not legacy_started:
                        self._publish(sid, 'preview_start', attempt, ordinal=0)
                        legacy_started = True
                    self._publish(sid, 'preview_delta', attempt, ordinal=0, text=body)
                    return
                self._publish(sid, body['kind'], attempt, ordinal=body['ordinal'],
                              **({'text': body['text']} if 'text' in body else {}))
            # An accepted-event handler may cancel before the provider starts.
            # Do not rely only on task cancellation at the next await boundary.
            authoritative = self.repository.load(sid)
            current = execution_for_request(authoritative, attempt['request_id'])[1]
            epoch = current['legacy_execution']['context_epoch'] if legacy else current['context_epoch']
            if current['status'] != 'pending' or epoch != authoritative['context_epoch']:
                return False
            with generation_scope(('character', sid, attempt['request_id']), attempt['request_id']):
                raw = await self.transport.generate(config, plan, report,
                                                    'stream' if mode == 'stream' else 'non_stream', preview)
            if legacy_started:
                self._publish(sid, 'preview_end', attempt, ordinal=0)
            self._publish(sid, 'validating', attempt)
            commit = commit_legacy if legacy else commit_generated
            group = self._transaction(sid, lambda s: commit(s, attempt['request_id'], raw, messages, entries))
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
                        attempt = execution_for_request(snapshot, group['request_id'])[1]
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
                self._refresh_contact(sid)
