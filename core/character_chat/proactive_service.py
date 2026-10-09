"""One event-driven idle/plan timer per session; never a paid polling loop."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from . import proactive_contact as domain
from .proactive_quota import ProactiveQuota
from .proactive_context import build_contact_context, parse_contact_plan
from .group_lifecycle import busy, current_attempt
from .group_records import pending_inputs, capacity_groups
from .group_views import public_group
from .limits import MAX_TURNS, MAX_ACTIONS, MAX_ATTEMPTS
from .models import CharacterSessionError, canonical_id
from .preferences import session_settings

COST_WARNING = '主动联系会额外调用模型，可能产生费用；每日限制仅统计次数，不代表金额或token上限。仅本地服务运行期间有效。'


class ProactiveContactService:
    def __init__(self, group_service, quota_path, *, clock=None, lease_seconds=30, late_seconds=60, sleep=None):
        self.groups = group_service
        self.repository = group_service.repository
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.quota = ProactiveQuota(quota_path, self.clock)
        self.lease_seconds, self.late_seconds = lease_seconds, late_seconds
        self.sleep = sleep or asyncio.sleep
        self.workers, self.signals, self.leases, self.idle_since = {}, {}, {}, {}
        self.reservations, self.warnings = {}, {}
        self.started, self.closed = False, False

    def _check(self, sid):
        self.groups._check(sid)
        if self.closed:
            raise CharacterSessionError('SERVICE_CLOSED')

    def view(self, sid):
        self._check(sid)
        session = self.repository.load(sid)
        supported = session.get('schema_version') == 2
        value = domain.settings(session) if supported else dict(domain.DEFAULTS, next_due_at=None, expires_at=None)
        setting_keys = ('enabled', 'paused', 'idle_seconds', 'max_contacts')
        due = value['next_due_at']
        if value['cycle_state'] == 'armed' and sid in self.idle_since:
            due = (self.idle_since[sid][1] + timedelta(seconds=value['idle_seconds'])).isoformat()
        return {'session_id': sid, 'revision': session['revision'], 'supported': supported,
                'settings': {k: value[k] for k in setting_keys}, 'state': value['cycle_state'],
                'authorization_revision': value['authorization_revision'], 'interaction_epoch': value['interaction_epoch'],
                'next_due_at': due, 'expires_at': value['expires_at'], 'cost_warning': COST_WARNING,
                'warning': self.warnings.get(sid) or self.quota.error or (None if supported else 'SCHEMA_READ_ONLY'),
                'quota': self.quota.snapshot()}

    def quota_settings(self, payload=None):
        return self.quota.snapshot() if payload is None else self.quota.configure(payload)

    def configure(self, sid, payload):
        self._check(sid)
        if not isinstance(payload, dict) or 'expected_revision' not in payload:
            raise CharacterSessionError('INVALID_REQUEST')
        patch = {k: v for k, v in payload.items() if k != 'expected_revision'}
        self.groups._transaction(sid, lambda s: domain.configure(s, payload['expected_revision'], patch))
        self.warnings.pop(sid, None)
        self.refresh(sid)
        return self.view(sid)

    def activity(self, sid, client_id):
        self._check(sid)
        canonical_id(client_id)
        value = self.view(sid)
        if not value['supported']:
            raise CharacterSessionError('SCHEMA_READ_ONLY')
        if value['settings']['enabled'] and not value['settings']['paused']:
            self.leases.setdefault(sid, {})[client_id] = self.clock() + timedelta(seconds=self.lease_seconds)
            self.idle_since.pop(sid, None)
            self.refresh(sid)
        return self.view(sid)

    def refresh(self, sid):
        if self.closed or not self.started:
            return
        try:
            session = self.repository.load(sid)
        except CharacterSessionError:
            old = self.reservations.pop(sid, None)
            if old:
                self._release(old['plan_id'], old['count'] - old['delivered'], old['day'])
            self.signals.setdefault(sid, asyncio.Event()).set()
            return
        if session.get('schema_version') != 2:
            return
        self._release_stale(sid, session)
        signal = self.signals.setdefault(sid, asyncio.Event())
        signal.set()
        value = domain.state(session)
        if value['cycle_state'] not in {'armed', 'planning', 'planned'} or not value['enabled'] or value['paused']:
            self.idle_since.pop(sid, None)
            return
        task = self.workers.get(sid)
        if task is None or task.done():
            self.workers[sid] = asyncio.create_task(self._run(sid))

    async def start(self):
        if self.started or self.closed:
            return
        self.started = True
        for sid in self.repository.session_ids():
            try:
                session = self.repository.load(sid)
                if session.get('schema_version') != 2:
                    continue
                old = domain.state(session).get('plan')
                if old or domain.state(session)['cycle_state'] in {'armed', 'planning', 'planned'}:
                    self.groups._transaction(sid, lambda s: domain.finish_cycle(s, 'idle'))
                    if old:
                        count = self.quota.reserved_contacts(old['plan_id'], old['quota_day'])
                        self._release(old['plan_id'], count - old['next_index'], old['quota_day'])
            except CharacterSessionError:
                self.warnings[sid] = 'CONTACT_UNAVAILABLE'

    async def close(self):
        if self.closed:
            return
        self.closed = True
        tasks = list(self.workers.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for sid in list(self.signals):
            try:
                session = self.repository.load(sid)
                if session.get('schema_version') == 2 and domain.state(session)['cycle_state'] in {'armed', 'planning', 'planned'}:
                    self.groups._transaction(sid, lambda s: domain.finish_cycle(s, 'idle'))
                    self._release_stale(sid, self.repository.load(sid))
            except CharacterSessionError:
                pass  # C5 shutdown cannot prevent ordinary chat shutdown.
        self.workers.clear(); self.leases.clear(); self.idle_since.clear()

    def _release(self, plan_id, undelivered, day):
        try:
            self.quota.release(plan_id, undelivered, day)
        except CharacterSessionError:
            pass  # A failed release remains conservatively occupied.

    def _release_stale(self, sid, session):
        old = self.reservations.get(sid)
        if not old:
            return
        plan = domain.state(session)['plan']
        if plan and plan['plan_id'] == old['plan_id']:
            old['delivered'] = plan['next_index']
            return
        # The normal completion clears its plan; account for committed refs,
        # while cancellation/new-input may have erased all prewritten content.
        delivered = sum(g.get('contact_ref', {}).get('plan_id') == old['plan_id'] for g in session['groups'])
        self._release(old['plan_id'], old['count'] - delivered, old['day'])
        self.reservations.pop(sid, None)

    def _finish(self, sid, warning=None, plan_id=None):
        def change(session):
            if plan_id is not None and domain.plan_current(session, plan_id) is None:
                return False
            return domain.finish_cycle(session)
        self.groups._transaction(sid, change)
        self.idle_since.pop(sid, None)
        if warning:
            self.warnings[sid] = warning
        self._release_stale(sid, self.repository.load(sid))

    def _block_until(self, sid, session):
        worker = self.groups.workers.get(sid)
        if busy(session) or pending_inputs(session) or (worker is not None and not worker.done()):
            return 'busy'
        now = self.clock()
        leases = self.leases.get(sid, {})
        for key in list(leases):
            if leases[key] <= now:
                leases.pop(key)
        return max(leases.values()) if leases else None

    async def _wait(self, sid, due=None):
        signal = self.signals[sid]
        if due is None:
            await signal.wait()
            return False
        delay = max(0, (due - self.clock()).total_seconds())
        sleeper = asyncio.create_task(self.sleep(delay))
        wake = asyncio.create_task(signal.wait())
        try:
            done, _ = await asyncio.wait((sleeper, wake), return_when=asyncio.FIRST_COMPLETED)
            return sleeper in done and (self.clock() - due).total_seconds() > self.late_seconds
        finally:
            sleeper.cancel(); wake.cancel()
            await asyncio.gather(sleeper, wake, return_exceptions=True)

    async def _plan(self, sid):
        async with self.groups.slots:
            session = self.repository.load(sid)
            value = domain.state(session)
            if value['cycle_state'] != 'armed' or not value['enabled'] or value['paused'] or self._block_until(sid, session):
                return
            if (len(capacity_groups(session)) >= MAX_TURNS or len(session['requests']) >= MAX_ACTIONS or
                    sum(len(a['attempts']) for a in session['requests']) >= MAX_ATTEMPTS):
                self._finish(sid, 'SESSION_LIMIT'); return
            config = self.groups.transport.snapshot()
            now = self.clock()
            quota = self.quota.snapshot()
            expires = min(now + timedelta(hours=2), datetime.fromisoformat(quota['resets_at']))
            maximum = min(value['max_contacts'], quota['contacts_remaining'])
            if not quota['available'] or quota['calls_remaining'] < 1 or maximum < 1:
                self._finish(sid, quota['error'] or 'CONTACT_QUOTA_EXHAUSTED'); return
            prefs = session_settings(session)
            preferences = self.groups.preference_loader(prefs) if prefs['enabled'] else []
            prompt, messages, entries, report = build_contact_context(session, maximum, int((expires - now).total_seconds()),
                config.get('budget_options'), preferences=preferences)
            plan_id = str(uuid4())
            day, count = self.quota.reserve(plan_id, maximum)
            if not count:
                self._finish(sid, 'CONTACT_QUOTA_EXHAUSTED'); return
            self.reservations[sid] = {'plan_id': plan_id, 'day': day, 'count': count, 'delivered': 0}
            plan = self.groups._transaction(sid, lambda s: domain.mark_planning(s, plan_id, day, expires, count, now,
                allowed_message_ids=messages, allowed_entry_ids=entries))
            if not plan:
                self._release_stale(sid, self.repository.load(sid)); return
            try:
                raw = await self.groups.transport.generate_contact(config, prompt, report)
                contacts = parse_contact_plan(raw, count, int((expires - now).total_seconds()))
                if self.clock() >= expires:
                    self._finish(sid, 'CONTACT_EXPIRED', plan_id); return
                saved = self.groups._transaction(sid, lambda s: domain.save_plan(s, plan_id, contacts, self.clock()))
                if saved:
                    self._release(plan_id, count - len(contacts), day)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._finish(sid, getattr(exc, 'code', 'PROVIDER_FAILED'), plan_id)
            finally:
                self._release_stale(sid, self.repository.load(sid))

    async def _run(self, sid):
        try:
            while not self.closed:
                self.signals[sid].clear()
                session = self.repository.load(sid)
                value = domain.state(session)
                self._release_stale(sid, session)
                if not value['enabled'] or value['paused'] or value['cycle_state'] not in {'armed', 'planned'}:
                    return
                plan = value['plan']
                now = self.clock()
                if plan and now >= datetime.fromisoformat(plan['expires_at']):
                    self._finish(sid, 'CONTACT_EXPIRED'); return
                blocked = self._block_until(sid, session)
                if blocked:
                    self.idle_since.pop(sid, None)
                    due = None if blocked == 'busy' else blocked
                    if plan:
                        expiry = datetime.fromisoformat(plan['expires_at'])
                        due = expiry if due is None else min(expiry, due)
                    if await self._wait(sid, due):
                        self._finish(sid, 'CONTACT_TIMER_LATE'); return
                    continue
                token = (value['interaction_epoch'], value['authorization_revision'])
                if sid not in self.idle_since or self.idle_since[sid][0] != token:
                    self.idle_since[sid] = (token, now)
                idle_due = self.idle_since[sid][1] + timedelta(seconds=value['idle_seconds'])
                due = idle_due
                if plan:
                    contact = plan['contacts'][plan['next_index']]
                    due = max(idle_due, datetime.fromisoformat(plan['planned_at']) + timedelta(seconds=contact['delay_seconds']))
                    due = min(due, datetime.fromisoformat(plan['expires_at']))
                if now < due:
                    if await self._wait(sid, due):
                        self._finish(sid, 'CONTACT_TIMER_LATE'); return
                    continue
                if plan:
                    group = self.groups._transaction(sid, lambda s: domain.commit_proactive_contact(s, plan['plan_id'], plan['next_index'], self.clock()))
                    if group:
                        attempt = current_attempt(self.repository.load(sid), group['request_id'])[1]
                        self.groups._publish(sid, 'group_saved', attempt, group=public_group(group), state=self.groups._event_state(sid))
                else:
                    await self._plan(sid)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            try:
                self._finish(sid, getattr(exc, 'code', 'CONTACT_UNAVAILABLE'))
            except CharacterSessionError:
                self.warnings[sid] = 'CONTACT_UNAVAILABLE'
        finally:
            if self.workers.get(sid) is asyncio.current_task():
                self.workers.pop(sid, None)
