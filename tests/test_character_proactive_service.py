import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.character_chat import proactive_contact as domain
from core.character_chat.group_service import CharacterGroupService
from core.character_chat.group_schema import validate_schema2
from core.character_chat.group_migration import convert_legacy_session
from core.character_chat.models import CharacterSessionError, create_session
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat.proactive_quota import ProactiveQuota
from core.character_chat.proactive_context import parse_contact_plan
from core.character_chat.proactive_service import ProactiveContactService
from tests.test_character_group_service import FakeGroupTransport
from tests.test_character_multibubble_protocol import result


class FakeContactTransport(FakeGroupTransport):
    def __init__(self):
        super().__init__()
        self.contact_calls = []
        self.contacts = [{'delay_seconds': 0, 'reply': result('主动问候')}]
        self.contact_started = asyncio.Event()
        self.contact_gate = asyncio.Event(); self.contact_gate.set()

    async def generate_contact(self, config, plan, report):
        self.contact_calls.append(json.loads(plan.user_prompt))
        self.contact_started.set()
        await self.contact_gate.wait()
        return json.dumps({'contacts': self.contacts}, ensure_ascii=False)


class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'quota.json'
        self.now = datetime(2026, 10, 9, tzinfo=timezone.utc)
        self.quota = ProactiveQuota(self.path, lambda: self.now)

    def test_reservations_release_and_forward_only_day(self):
        self.quota.configure({'call_limit': 2, 'contact_limit': 3})
        day, count = self.quota.reserve('one', 2)
        self.assertEqual(2, count)
        self.assertEqual((day, 1), self.quota.reserve('two', 2))
        self.assertEqual((day, 0), self.quota.reserve('three', 1))
        self.quota.release('one', 1, day); self.quota.release('one', 1, day)
        self.assertEqual(2, self.quota.snapshot()['contacts_used'])
        self.assertEqual(2, ProactiveQuota(self.path, lambda: self.now).snapshot()['calls_used'])
        self.now -= timedelta(days=1)
        self.assertEqual(day, self.quota.snapshot()['day'])
        self.now += timedelta(days=2)
        self.assertEqual(0, self.quota.snapshot()['calls_used'])

    def test_corrupt_and_failed_write_never_reset(self):
        self.path.write_text('{broken', encoding='utf-8')
        quota = ProactiveQuota(self.path)
        self.assertFalse(quota.snapshot()['available'])
        with self.assertRaises(CharacterSessionError):
            quota.reserve('new', 1)
        self.assertEqual('{broken', self.path.read_text(encoding='utf-8'))
        self.path.unlink()
        with patch('core.character_chat.proactive_quota.os.replace', side_effect=OSError()):
            with self.assertRaises(CharacterSessionError):
                self.quota.reserve('failure', 1)
        self.assertFalse(self.quota.snapshot()['available'])

    def test_plan_boundary_empty_multi_negative_order_and_total(self):
        self.assertEqual([], parse_contact_plan('{"contacts":[]}', 2, 100))
        good = {'contacts': [{'delay_seconds': 0, 'reply': result('甲')}, {'delay_seconds': 2, 'reply': result('乙')}]}
        self.assertEqual(2, len(parse_contact_plan(json.dumps(good), 2, 100)))
        for delays in ((-1,), (2, 1), (100,)):
            bad = {'contacts': [{'delay_seconds': d, 'reply': result('x')} for d in delays]}
            with self.assertRaises(CharacterSessionError):
                parse_contact_plan(json.dumps(bad), 2, 100)
        large = {'contacts': [{'delay_seconds': 0, 'reply': result('x' * 5000)}, {'delay_seconds': 1, 'reply': result('y' * 5000)}]}
        with self.assertRaises(CharacterSessionError):
            parse_contact_plan(json.dumps(large), 2, 100)


class ContactServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.repo = CharacterSessionRepository(Path(self.temp.name) / 'sessions', validator=validate_schema2, supported_schemas=(2,))
        self.transport = FakeContactTransport()
        self.groups = CharacterGroupService(self.repo, self.transport)
        self.contact = ProactiveContactService(self.groups, Path(self.temp.name) / 'quota.json', lease_seconds=0.1)
        self.groups.proactive = self.contact
        self.addAsyncCleanup(self.groups.close)
        self.addAsyncCleanup(self.contact.close)
        self.sid = self.create()
        await self.groups.start(); await self.contact.start()

    def create(self):
        session = convert_legacy_session(create_session(str(uuid4()), {'name': '合成', 'description': '固定'}, {'kind': 'character', 'key': '合成'}))
        self.repo.create(session)
        return session['session_id']

    def configure(self, sid=None, **values):
        sid = sid or self.sid
        return self.contact.configure(sid, {'expected_revision': self.repo.load(sid)['revision'], **values})

    async def chat(self, sid=None):
        sid = sid or self.sid
        await self.groups.send(sid, {'client_action_id': str(uuid4()), 'expected_revision': self.repo.load(sid)['revision'], 'content': '正式玩家消息'}, 'instant')
        await self.groups.wait_idle(sid)
        self.contact.refresh(sid)

    async def until(self, predicate, timeout=3):
        async with asyncio.timeout(timeout):
            while not predicate():
                await asyncio.sleep(0.01)

    def proactive_groups(self, sid=None):
        return [g for g in self.repo.load(sid or self.sid)['groups'] if g.get('origin') == 'proactive']

    async def test_default_off_and_enabling_waits_for_next_formal_input(self):
        await self.chat()
        self.assertEqual([], self.transport.contact_calls)
        self.configure(enabled=True, idle_seconds=1)
        await asyncio.sleep(0.05)
        self.assertEqual('idle', self.contact.view(self.sid)['state'])
        self.assertEqual([], self.transport.contact_calls)
        await self.chat()
        await self.until(lambda: len(self.proactive_groups()) == 1)
        self.assertEqual(1, len(self.transport.contact_calls))
        context = self.transport.contact_calls[0]
        self.assertNotIn('current_user_messages', context)
        self.assertNotIn('current_ooc_notes', context)
        self.assertEqual([], self.proactive_groups()[0]['input_ids'])
        self.assertEqual('instant', self.proactive_groups()[0]['display_mode'])
        self.assertEqual('exhausted', self.contact.view(self.sid)['state'])
        self.assertNotIn('主动问候', json.dumps(self.contact.view(self.sid), ensure_ascii=False))

    async def test_empty_and_multiple_contacts_are_one_call(self):
        self.configure(enabled=True, idle_seconds=1)
        self.transport.contacts = []
        await self.chat()
        await self.until(lambda: self.contact.view(self.sid)['state'] == 'exhausted')
        self.assertEqual(1, len(self.transport.contact_calls))
        self.assertEqual(0, self.contact.quota.snapshot()['contacts_used'])
        self.transport.contacts = [{'delay_seconds': 0, 'reply': result('甲')}, {'delay_seconds': 0, 'reply': result('乙')}]
        await self.chat()
        await self.until(lambda: len(self.proactive_groups()) == 2)
        self.assertEqual(2, len(self.transport.contact_calls))
        self.assertEqual(2, self.contact.quota.snapshot()['contacts_used'])

    async def test_edit_lease_delays_idle_without_draft_upload(self):
        self.configure(enabled=True, idle_seconds=1)
        await self.chat()
        await asyncio.sleep(0.6)
        self.contact.activity(self.sid, str(uuid4()))
        await asyncio.sleep(0.6)
        self.assertEqual([], self.transport.contact_calls)
        await self.until(lambda: len(self.proactive_groups()) == 1)

    async def test_late_provider_after_disable_cannot_save_or_charge_again(self):
        self.configure(enabled=True, idle_seconds=1)
        self.transport.contact_gate.clear()
        await self.chat()
        await asyncio.wait_for(self.transport.contact_started.wait(), 3)
        self.configure(enabled=False)
        self.transport.contact_gate.set()
        await self.until(lambda: self.sid not in self.contact.workers)
        self.assertEqual([], self.proactive_groups())
        self.assertEqual(1, self.contact.quota.snapshot()['calls_used'])
        self.assertEqual(0, self.contact.quota.snapshot()['contacts_used'])

    async def test_two_sessions_share_last_quota_and_restart_does_not_call(self):
        second = self.create()
        self.contact.quota_settings({'call_limit': 1, 'contact_limit': 1})
        self.configure(enabled=True, idle_seconds=1)
        self.configure(second, enabled=True, idle_seconds=1)
        await self.chat(); await self.chat(second)
        await self.until(lambda: self.contact.view(self.sid)['state'] == self.contact.view(second)['state'] == 'exhausted')
        self.assertEqual(1, len(self.transport.contact_calls))
        self.assertEqual(1, len(self.proactive_groups()) + len(self.proactive_groups(second)))
        await self.contact.close()
        restarted = ProactiveContactService(self.groups, Path(self.temp.name) / 'quota.json')
        await restarted.start()
        self.assertEqual(1, len(self.transport.contact_calls))
        await restarted.close()

    async def test_new_epoch_discards_late_plan_but_preserves_new_cycle(self):
        self.configure(enabled=True, idle_seconds=1)
        self.transport.contact_gate.clear()
        await self.chat()
        await asyncio.wait_for(self.transport.contact_started.wait(), 3)
        epoch = self.repo.load(self.sid)['extensions']['proactive_contact']['interaction_epoch']
        await self.chat()
        self.transport.contact_gate.set()
        await self.until(lambda: self.sid not in self.contact.reservations)
        self.assertEqual('armed', self.contact.view(self.sid)['state'])
        self.assertGreater(self.contact.view(self.sid)['interaction_epoch'], epoch)
        self.assertEqual([], self.proactive_groups())
        self.assertEqual(1, len(self.transport.contact_calls))
        self.configure(enabled=False)

    async def test_restart_drops_prepared_plan_without_provider_or_disabled_file_write(self):
        self.configure(enabled=True, idle_seconds=1)
        plan_id = str(uuid4())
        now = datetime.now(timezone.utc)
        day, count = self.contact.quota.reserve(plan_id, 2)
        def prepare(session):
            domain.on_user_input(session)
            domain.mark_planning(session, plan_id, day, now + timedelta(hours=1), count, now)
        self.groups._transaction(self.sid, prepare)
        self.groups._transaction(self.sid, lambda s: domain.save_plan(s, plan_id, [{'delay_seconds': 100, 'reply': result('不应补发')}], now))
        disabled = self.create()
        before = self.repo.load(disabled)['revision']
        restarted = ProactiveContactService(self.groups, Path(self.temp.name) / 'quota.json')
        await restarted.start()
        self.assertEqual([], self.transport.contact_calls)
        self.assertEqual('idle', restarted.view(self.sid)['state'])
        self.assertTrue(restarted.view(self.sid)['settings']['enabled'])
        self.assertIsNone(self.repo.load(self.sid)['extensions']['proactive_contact']['plan'])
        self.assertEqual(before, self.repo.load(disabled)['revision'])
        self.assertEqual(1, restarted.quota.snapshot()['calls_used'])
        self.assertEqual(0, restarted.quota.snapshot()['contacts_used'])
        await restarted.close()

    async def test_late_timer_stops_cycle_without_paid_call(self):
        now = datetime.now(timezone.utc)
        self.contact.clock = lambda: now
        async def late_sleep(seconds):
            nonlocal now
            now += timedelta(seconds=seconds + 61)
            await asyncio.sleep(0)
        self.contact.sleep = late_sleep
        self.configure(enabled=True, idle_seconds=1)
        await self.chat()
        await self.until(lambda: self.contact.view(self.sid)['state'] == 'exhausted')
        self.assertEqual([], self.transport.contact_calls)
        self.assertEqual('CONTACT_TIMER_LATE', self.contact.view(self.sid)['warning'])
