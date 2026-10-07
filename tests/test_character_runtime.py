import asyncio
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.character_chat.models import create_session, CharacterSessionError
from core.character_chat.group_migration import convert_legacy_session
from core.character_chat.provider_slots import ProviderSlots
from core.character_chat.runtime import CharacterRuntime, runtime_lifespan
from tests.test_character_group_service import FakeGroupTransport
from tests.test_character_chat_lifecycle import FakeTransport
from core.character_chat.group_lifecycle import accept_input, claim_inputs, fail_generation
from unittest.mock import patch


class SlotTests(unittest.IsolatedAsyncioTestCase):
    async def test_shared_limit_and_fifo_without_blocking_loop(self):
        slots = ProviderSlots(4)
        for _ in range(4):
            self.assertTrue(slots.acquire())
        self.assertFalse(slots.acquire())
        first = asyncio.create_task(slots.acquire_async())
        second = asyncio.create_task(slots.acquire_async())
        await asyncio.sleep(0)
        self.assertFalse(first.done())
        slots.release()
        await first
        self.assertFalse(second.done())
        self.assertFalse(slots.acquire())
        slots.release()
        await second
        for _ in range(4):
            slots.release()
        with self.assertRaises(ValueError):
            slots.release()

    async def test_cancel_before_and_after_scheduled_grant_does_not_leak(self):
        for before_release in (True, False):
            slots = ProviderSlots(1); slots.acquire()
            waiter = asyncio.create_task(slots.acquire_async())
            await asyncio.sleep(0)
            if before_release:
                waiter.cancel(); await asyncio.sleep(0)
            slots.release()
            waiter.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await waiter
            await asyncio.sleep(0)
            self.assertTrue(slots.acquire())
            slots.release()

    async def test_cancel_after_result_before_context_body_returns_slot(self):
        slots = ProviderSlots(1); slots.acquire()
        task = asyncio.create_task(slots.acquire_async())
        await asyncio.sleep(0)
        slots.release()
        # Grant is already scheduled; cancellation runs before await resumes.
        asyncio.get_running_loop().call_soon(task.cancel)
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(slots.acquire())
        slots.release()


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.transport = FakeGroupTransport()
        self.runtime = CharacterRuntime(Path(self.temp.name), transport=self.transport)
        self.addAsyncCleanup(self.runtime.close)

    def create(self, version):
        value = create_session(str(uuid4()), {'name': '合成', 'description': '固定'},
                               {'kind': 'character', 'key': '合成'})
        if version == 2:
            value = convert_legacy_session(value)
        self.runtime.repository.create(value)
        return value['session_id']

    async def test_lifecycle_guard_single_process_and_repository_formats(self):
        old = self.create(1); new = self.create(2)
        before = {sid: (Path(self.temp.name) / f'{sid}.json').read_bytes() for sid in (old, new)}
        with self.assertRaisesRegex(CharacterSessionError, 'SERVICE_UNAVAILABLE'):
            self.runtime.require_groups()
        await self.runtime.start()
        self.assertIs(self.runtime.groups, self.runtime.require_groups())
        self.assertIs(self.runtime.legacy.slots, self.runtime.groups.slots)
        for sid in (old, new):
            self.assertEqual(before[sid], (Path(self.temp.name) / f'{sid}.json').read_bytes())
        await self.runtime.close()
        with self.assertRaisesRegex(CharacterSessionError, 'SERVICE_UNAVAILABLE'):
            self.runtime.require_groups()

    async def test_mixed_old_reservations_limit_new_worker_to_remaining_slot(self):
        await self.runtime.start()
        jobs = []
        for _ in range(3):
            sid = self.create(1)
            self.runtime.legacy.begin(sid, {'client_action_id': str(uuid4()),
                'expected_revision': 0, 'operation': 'send', 'content': '旧输入'})
            jobs.append(sid)
        self.transport.gate.clear()
        first = self.create(2); second = self.create(2)
        for sid in (first, second):
            await self.runtime.groups.send(sid, {'client_action_id': str(uuid4()),
                'expected_revision': 0, 'content': '新输入'})
        await asyncio.wait_for(self.transport.started.wait(), 2)
        await asyncio.sleep(.02)
        self.assertEqual(1, len(self.transport.calls))
        self.assertEqual(1, self.runtime.groups.view(second)['queued_count'])
        sid = self.create(1)
        with self.assertRaisesRegex(CharacterSessionError, 'CAPACITY_LIMIT'):
            self.runtime.legacy.begin(sid, {'client_action_id': str(uuid4()),
                'expected_revision': 0, 'operation': 'send', 'content': '第五'})
        self.transport.gate.set()
        await self.runtime.groups.wait_idle(first)
        await self.runtime.groups.wait_idle(second)
        self.assertEqual(2, len(self.transport.calls))
        await self.runtime.close()
        for sid in jobs:
            value = self.runtime.repository.load(sid)
            self.assertEqual('interrupted', value['requests'][0]['attempts'][0]['status'])
            self.assertEqual([], value['turns'])
        self.assertEqual(0, self.runtime.slots._used)

    async def test_multiprocess_does_not_start_c4_recovery_or_calls(self):
        self.create(2)
        self.runtime.workers = '2'
        await self.runtime.start()
        self.assertFalse(self.runtime.groups.started)
        with self.assertRaisesRegex(CharacterSessionError, 'SERVICE_UNAVAILABLE'):
            self.runtime.require_groups()
        self.assertEqual([], self.transport.calls)

    async def test_shutdown_running_old_request_interrupts_without_formal_reply(self):
        transport = FakeTransport(); transport.gate = asyncio.Event(); transport.started = asyncio.Event()
        self.runtime.legacy.transport = transport
        await self.runtime.start()
        sid = self.create(1)
        job = self.runtime.legacy.begin(sid, {'client_action_id': str(uuid4()),
            'expected_revision': 0, 'operation': 'send', 'content': '未完成'})['job']
        task = asyncio.create_task(self.runtime.legacy.execute(job['request_id'], lambda *_: None))
        await asyncio.wait_for(transport.started.wait(), 2)
        await self.runtime.close()
        await task
        value = self.runtime.repository.load(sid)
        self.assertEqual('interrupted', value['requests'][0]['attempts'][0]['status'])
        self.assertEqual([], value['turns'])
        self.assertEqual(0, self.runtime.slots._used)
        self.assertEqual({}, self.runtime.legacy.tasks)
        with self.assertRaisesRegex(CharacterSessionError, 'SERVICE_UNAVAILABLE'):
            self.runtime.legacy.metadata(sid, value['revision'], title='已关闭')

    async def test_legacy_recovery_does_not_modify_schema2_pending_attempt(self):
        sid = self.create(1)
        self.runtime.legacy.begin(sid, {'client_action_id': str(uuid4()),
            'expected_revision': 0, 'operation': 'send', 'content': '旧待处理'})
        old = self.runtime.repository.load(sid)
        converted = convert_legacy_session(old)
        # Conversion is synthetic only; give it an independent file identity.
        converted['session_id'] = str(uuid4())
        self.runtime.repository.create(converted)
        path = Path(self.temp.name) / f"{converted['session_id']}.json"
        before = path.read_bytes()
        self.runtime.legacy.recover_pending()
        self.assertEqual(before, path.read_bytes())

    async def test_close_waiting_retry_and_not_yet_started_regenerate(self):
        for operation in ('retry', 'regenerate'):
            with self.subTest(operation=operation):
                runtime = CharacterRuntime(Path(self.temp.name) / operation, transport=FakeGroupTransport())
                self.addAsyncCleanup(runtime.close)
                await runtime.start()
                value = convert_legacy_session(create_session(str(uuid4()), {'name': '合成', 'description': '固定'},
                    {'kind': 'character', 'key': '合成'}))
                sid = value['session_id']; runtime.repository.create(value)
                if operation == 'retry':
                    action = runtime.groups._transaction(sid, lambda s: accept_input(s,
                        {'client_action_id': str(uuid4()), 'expected_revision': 0, 'content': '输入'})[0])
                    attempt = runtime.groups._transaction(sid, lambda s: claim_inputs(s))
                    aid, rid = action['action_id'], attempt['request_id']
                    runtime.groups._transaction(sid, lambda s: fail_generation(s, rid, 'failed', 'PROVIDER_FAILED'))
                else:
                    await runtime.groups.send(sid, {'client_action_id': str(uuid4()), 'expected_revision': 0, 'content': '输入'})
                    await runtime.groups.wait_idle(sid)
                for _ in range(4):
                    runtime.slots.acquire()
                if operation == 'retry':
                    await runtime.groups.retry(sid, aid, {'expected_revision': runtime.repository.load(sid)['revision'],
                        'retry_of': rid, 'retry_token': str(uuid4())})
                    await asyncio.sleep(0)  # Waiting inside slot admission.
                else:
                    stored = runtime.repository.load(sid)
                    await runtime.groups.batch(sid, {'client_action_id': str(uuid4()), 'expected_revision': stored['revision'],
                        'operation': 'regenerate', 'target_group_id': stored['groups'][-1]['group_id']})
                    # Close before the scheduled worker enters its coroutine.
                calls = len(runtime.groups.transport.calls)
                await runtime.close()
                stored = runtime.repository.load(sid)
                self.assertEqual('interrupted', stored['requests'][-1]['attempts'][-1]['status'])
                self.assertFalse(any(g['status'] == 'generating' for g in stored['groups']))
                self.assertEqual(calls, len(runtime.groups.transport.calls))
                if operation == 'regenerate':
                    self.assertEqual('complete', stored['groups'][0]['status'])
                for _ in range(4):
                    runtime.slots.release()

    async def test_shutdown_persistence_error_still_releases_old_slots(self):
        await self.runtime.start(); sid = self.create(1)
        self.runtime.legacy.begin(sid, {'client_action_id': str(uuid4()), 'expected_revision': 0,
            'operation': 'send', 'content': '输入'})
        with patch.object(self.runtime.repository, '_write', side_effect=CharacterSessionError('PERSISTENCE_FAILED')):
            with self.assertRaisesRegex(CharacterSessionError, 'PERSISTENCE_FAILED'):
                await self.runtime.close()
        self.assertEqual({}, self.runtime.legacy.jobs)
        self.assertEqual(0, self.runtime.slots._used)


class LifespanTests(unittest.TestCase):
    def test_app_owns_runtime_on_one_loop_and_closes_it(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = CharacterRuntime(Path(directory), transport=FakeGroupTransport())
            app = FastAPI(lifespan=runtime_lifespan(lambda: runtime))
            @app.get('/probe')
            async def probe():
                return {'started': app.state.character_runtime.require_groups().started}
            self.assertFalse(runtime.started)
            with TestClient(app) as client:
                self.assertEqual({'started': True}, client.get('/probe').json())
            self.assertTrue(runtime.closed)
