import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.character_chat.group_service import CharacterGroupService
from core.character_chat.group_schema import validate_schema2
from core.character_chat.group_migration import convert_legacy_session
from core.character_chat.group_lifecycle import busy
from core.character_chat.models import create_session, CharacterSessionError
from core.character_chat.repository import CharacterSessionRepository
from tests.test_character_multibubble_protocol import result


class FakeGroupTransport:
    def __init__(self):
        self.calls = []; self.gate = asyncio.Event(); self.gate.set()
        self.started = asyncio.Event(); self.fail = False
        self.value = result('甲', '乙')
    def snapshot(self):
        return {'model': 'synthetic', 'context_window': 32768}
    async def generate(self, config, plan, report, delivery, emit):
        self.calls.append({'data': json.loads(plan.user_prompt), 'delivery': delivery})
        self.started.set()
        if delivery == 'stream':
            for index, text in enumerate(('甲', '乙')):
                emit({'kind': 'preview_start', 'ordinal': index})
                emit({'kind': 'preview_delta', 'ordinal': index, 'text': text})
                emit({'kind': 'preview_end', 'ordinal': index})
        await self.gate.wait()
        if self.fail:
            raise CharacterSessionError('PROVIDER_FAILED')
        return json.dumps(self.value)


class GroupServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.repo = CharacterSessionRepository(Path(self.temp.name), validator=validate_schema2, supported_schemas=(2,))
        self.sid = self.create()
        self.transport = FakeGroupTransport()
        self.service = CharacterGroupService(self.repo, self.transport)
        self.addAsyncCleanup(self.service.close)
        self.events = []
        self.service.subscribe(self.sid, lambda name, body: self.events.append((name, body)))

    def create(self):
        value = convert_legacy_session(create_session(str(uuid4()), {'name': '合成', 'description': '固定'},
                                                        {'kind': 'character', 'key': '合成'}))
        self.repo.create(value); return value['session_id']

    def payload(self, text, sid=None):
        return {'client_action_id': str(uuid4()), 'expected_revision': self.repo.load(sid or self.sid)['revision'], 'content': text}

    async def started(self):
        await asyncio.wait_for(self.transport.started.wait(), 2)

    async def idle(self, sid=None):
        await asyncio.wait_for(self.service.wait_idle(sid or self.sid), 3)

    async def test_stream_preview_then_one_formal_batch_no_replay_or_auto_continuation(self):
        self.transport.gate.clear()
        await self.service.send(self.sid, self.payload('输入'))
        await self.started()
        before = self.service.view(self.sid)
        self.assertEqual(1, len(before['messages'])); self.assertEqual(0, before['unread_count'])
        self.assertEqual(2, sum(name == 'preview_start' for name, _ in self.events))
        self.transport.gate.set(); await self.idle()
        view = self.service.view(self.sid)
        self.assertEqual(['输入', '甲', '乙'], [m['message']['content'] for m in view['messages']])
        self.assertEqual(2, view['unread_count']); self.assertEqual(1, len(self.transport.calls))
        self.assertEqual(1, sum(name == 'group_saved' for name, _ in self.events))
        current = [body['seq'] for name, body in self.events if body['request_id']]
        self.assertEqual(list(range(1, len(current) + 1)), current)

    async def test_inputs_during_generation_coalesce_into_single_next_call(self):
        self.transport.gate.clear()
        await self.service.send(self.sid, self.payload('原'))
        await self.started()
        await self.service.send(self.sid, self.payload('X'))
        await self.service.send(self.sid, self.payload('Y'))
        self.assertEqual(2, self.service.view(self.sid)['queued_count'])
        self.transport.gate.set(); await self.idle()
        self.assertEqual(2, len(self.transport.calls))
        self.assertEqual(['原'], [m['content'] for m in self.transport.calls[0]['data']['current_user_messages']])
        self.assertEqual(['X', 'Y'], [m['content'] for m in self.transport.calls[1]['data']['current_user_messages']])

    async def test_gaps_continue_without_subscriber_and_read_ack_is_monotone(self):
        saved = asyncio.Event()
        detach = self.service.subscribe(self.sid, lambda n, b: saved.set() if n == 'group_saved' else None)
        await self.service.send(self.sid, self.payload('输入'), 'gaps')
        await asyncio.wait_for(saved.wait(), 2)
        view = self.service.view(self.sid)
        self.assertEqual('delivering', view['busy_group']['status'])
        self.assertEqual(1, view['busy_group']['delivered_count'])
        self.assertEqual(1, len(view['busy_group']['bubbles']))
        detach(); await self.idle()
        view = self.service.view(self.sid)
        self.assertIsNone(view['busy_group']); self.assertEqual(2, view['unread_count'])
        self.assertEqual('non_stream', self.transport.calls[0]['delivery'])
        seq = view['messages'][-1]['message']['seq']
        self.assertEqual(0, self.service.read(self.sid, seq)['unread_count'])
        self.assertFalse(self.service.read(self.sid, seq - 1)['changed'])

    async def test_failed_preview_does_not_save_or_restart_queue(self):
        self.transport.gate.clear(); self.transport.fail = True
        await self.service.send(self.sid, self.payload('原')); await self.started()
        await self.service.send(self.sid, self.payload('X'))
        self.transport.gate.set(); await self.idle()
        self.assertEqual(1, len(self.transport.calls))
        self.assertEqual(['原', 'X'], [m['message']['content'] for m in self.service.view(self.sid)['messages']])
        self.assertEqual(2, self.service.view(self.sid)['queued_count'])
        self.transport.fail = False
        await self.service.send(self.sid, self.payload('明确继续')); await self.idle()
        self.assertEqual(['原', 'X', '明确继续'], [m['content'] for m in self.transport.calls[1]['data']['current_user_messages']])

    async def test_cancel_preserves_input_and_waits_for_explicit_retry(self):
        self.transport.gate.clear()
        action = await self.service.send(self.sid, self.payload('原')); await self.started()
        group = busy(self.repo.load(self.sid)); rid = group['request_id']
        self.assertTrue(self.service.cancel(self.sid, rid)['cancelled']); await self.idle()
        self.assertEqual(1, len(self.transport.calls)); self.assertEqual(1, self.service.view(self.sid)['queued_count'])
        self.transport.gate.set()
        payload = {'expected_revision': self.repo.load(self.sid)['revision'], 'retry_of': rid, 'retry_token': str(uuid4())}
        retry = await self.service.retry(self.sid, action['action_id'], payload); await self.idle()
        again = await self.service.retry(self.sid, action['action_id'], payload)
        self.assertEqual(retry['request_id'], again['request_id']); self.assertEqual(2, len(self.transport.calls))
        self.assertEqual(1, len(self.repo.load(self.sid)['inputs']))

    async def test_display_change_only_applies_to_next_group(self):
        self.transport.gate.clear()
        await self.service.send(self.sid, self.payload('原'), 'stream'); await self.started()
        await self.service.send(self.sid, self.payload('下一条'), 'instant')
        self.transport.gate.set(); await self.idle()
        self.assertEqual(['stream', 'non_stream'], [c['delivery'] for c in self.transport.calls])
        self.assertEqual(['stream', 'instant'], [g['display_mode'] for g in self.repo.load(self.sid)['groups']])

    async def test_four_slots_fifth_input_saved_not_claimed_then_fairly_runs(self):
        self.transport.gate.clear()
        sids = [self.sid] + [self.create() for _ in range(4)]
        for sid in sids: await self.service.send(sid, self.payload('输入', sid))
        for _ in range(100):
            if len(self.transport.calls) == 4: break
            await asyncio.sleep(.005)
        self.assertEqual(4, len(self.transport.calls))
        self.assertIsNone(busy(self.repo.load(sids[-1])))
        self.assertEqual(1, self.service.view(sids[-1])['queued_count'])
        self.transport.gate.set()
        await asyncio.gather(*(self.idle(sid) for sid in sids))
        self.assertEqual(5, len(self.transport.calls))

    async def test_shutdown_and_startup_resume_valid_tail_without_new_provider_call(self):
        saved = asyncio.Event()
        self.service.subscribe(self.sid, lambda n, b: saved.set() if n == 'group_saved' else None)
        await self.service.send(self.sid, self.payload('输入'), 'gaps')
        await asyncio.wait_for(saved.wait(), 2); await self.service.close()
        before = self.repo.load(self.sid)
        self.assertEqual(1, before['groups'][0]['delivered_count'])
        next_transport = FakeGroupTransport(); resumed = CharacterGroupService(self.repo, next_transport)
        self.addAsyncCleanup(resumed.close)
        await resumed.start(); await asyncio.wait_for(resumed.wait_idle(self.sid), 3)
        self.assertEqual([], next_transport.calls)
        self.assertEqual(2, self.repo.load(self.sid)['groups'][0]['delivered_count'])
        self.assertEqual(2, resumed.view(self.sid)['unread_count'])

    async def test_shutdown_pending_becomes_interrupted_without_automatic_restart(self):
        self.transport.gate.clear()
        await self.service.send(self.sid, self.payload('输入')); await self.started(); await self.service.close()
        self.assertEqual('interrupted', self.repo.load(self.sid)['groups'][0]['status'])
        resumed = CharacterGroupService(self.repo, FakeGroupTransport()); self.addAsyncCleanup(resumed.close)
        await resumed.start(); await asyncio.sleep(.02)
        self.assertEqual({}, resumed.workers); self.assertEqual([], resumed.transport.calls)

    async def test_bad_subscriber_does_not_change_saved_result(self):
        def broken(*args): raise RuntimeError('subscriber gone')
        self.service.subscribe(self.sid, broken)
        await self.service.send(self.sid, self.payload('输入'), 'instant'); await self.idle()
        self.assertEqual('complete', self.repo.load(self.sid)['groups'][0]['status'])

    async def test_save_failure_never_broadcasts_formal_messages(self):
        original = self.repo._write
        def failed(value):
            if any(g['status'] == 'complete' for g in value['groups']):
                raise CharacterSessionError('PERSISTENCE_FAILED')
            return original(value)
        with patch.object(self.repo, '_write', side_effect=failed):
            await self.service.send(self.sid, self.payload('输入')); await self.idle()
        self.assertFalse(any(n == 'group_saved' for n, _ in self.events))
        self.assertEqual(1, len(self.service.view(self.sid)['messages']))
        self.assertEqual('failed', self.repo.load(self.sid)['groups'][0]['status'])

    async def test_cancel_winning_before_provider_starts_makes_zero_calls(self):
        self.service.subscribe(self.sid, lambda n, b: self.service.cancel(self.sid, b['request_id']) if n == 'accepted' else None)
        await self.service.send(self.sid, self.payload('输入')); await self.idle()
        self.assertEqual([], self.transport.calls)
        self.assertEqual('cancelled', self.repo.load(self.sid)['groups'][0]['status'])

    async def test_idempotent_send_does_not_restart_provider(self):
        payload = self.payload('输入')
        first = await self.service.send(self.sid, payload); await self.idle()
        again = await self.service.send(self.sid, payload); await self.idle()
        self.assertEqual(first['action_id'], again['action_id'])
        self.assertEqual(1, len(self.transport.calls)); self.assertEqual(1, len(self.repo.load(self.sid)['inputs']))

    async def test_input_during_gaps_waits_for_batch_end_before_next_request(self):
        saved = asyncio.Event()
        self.service.subscribe(self.sid, lambda n, b: saved.set() if n == 'group_saved' else None)
        await self.service.send(self.sid, self.payload('原'), 'gaps'); await asyncio.wait_for(saved.wait(), 2)
        await self.service.send(self.sid, self.payload('X'), 'instant')
        self.assertEqual(1, len(self.transport.calls))
        await self.idle()
        self.assertEqual(2, len(self.transport.calls))
        self.assertEqual(['原', '甲', '乙'], [m['content'] for m in self.transport.calls[1]['data']['history']])

    async def test_tail_persistence_failure_keeps_candidate_for_restart(self):
        original = self.repo._write
        def failed(value):
            if any(g['status'] == 'complete' for g in value['groups']):
                raise CharacterSessionError('PERSISTENCE_FAILED')
            return original(value)
        with patch.object(self.repo, '_write', side_effect=failed):
            await self.service.send(self.sid, self.payload('输入'), 'gaps'); await self.idle()
        self.assertIn(self.sid, self.service.blocked)
        group = self.repo.load(self.sid)['groups'][0]
        self.assertEqual('delivering', group['status']); self.assertEqual(1, group['delivered_count'])
        self.assertEqual(1, sum(n == 'group_saved' for n, _ in self.events))
        await self.service.close()
        resumed = CharacterGroupService(self.repo, FakeGroupTransport()); self.addAsyncCleanup(resumed.close)
        await resumed.start(); await asyncio.wait_for(resumed.wait_idle(self.sid), 3)
        self.assertEqual('complete', self.repo.load(self.sid)['groups'][0]['status'])
        self.assertEqual([], resumed.transport.calls)

    async def test_immediate_cancel_retry_does_not_lose_worker_wakeup(self):
        self.transport.gate.clear()
        action = await self.service.send(self.sid, self.payload('原')); await self.started()
        rid = busy(self.repo.load(self.sid))['request_id']
        self.service.cancel(self.sid, rid)
        await self.service.retry(self.sid, action['action_id'], {
            'expected_revision': self.repo.load(self.sid)['revision'], 'retry_of': rid, 'retry_token': str(uuid4())})
        self.transport.gate.set(); await self.idle()
        self.assertEqual(2, len(self.transport.calls)); self.assertIsNone(busy(self.repo.load(self.sid)))
        self.assertEqual(1, len(self.repo.load(self.sid)['inputs']))

    async def test_immediate_cancel_send_preserves_continue_intent(self):
        self.transport.gate.clear()
        await self.service.send(self.sid, self.payload('原')); await self.started()
        rid = busy(self.repo.load(self.sid))['request_id']
        self.service.cancel(self.sid, rid)
        await self.service.send(self.sid, self.payload('明确继续'))
        self.transport.gate.set(); await self.idle()
        self.assertEqual(2, len(self.transport.calls)); self.assertIsNone(busy(self.repo.load(self.sid)))
        self.assertEqual(['原', '明确继续'], [m['content'] for m in self.transport.calls[1]['data']['current_user_messages']])

    async def test_restart_delivers_tail_but_does_not_charge_for_old_queued_input(self):
        saved = asyncio.Event()
        self.service.subscribe(self.sid, lambda n, b: saved.set() if n == 'group_saved' else None)
        await self.service.send(self.sid, self.payload('原'), 'gaps'); await asyncio.wait_for(saved.wait(), 2)
        await self.service.send(self.sid, self.payload('旧队列X'))
        await self.service.close()
        resumed = CharacterGroupService(self.repo, FakeGroupTransport()); self.addAsyncCleanup(resumed.close)
        await resumed.start(); await asyncio.wait_for(resumed.wait_idle(self.sid), 3)
        self.assertEqual([], resumed.transport.calls)
        self.assertEqual('complete', self.repo.load(self.sid)['groups'][0]['status'])
        self.assertEqual(1, resumed.view(self.sid)['queued_count'])
        await resumed.send(self.sid, self.payload('明确继续Y')); await asyncio.wait_for(resumed.wait_idle(self.sid), 3)
        self.assertEqual(['旧队列X', '明确继续Y'], [m['content'] for m in resumed.transport.calls[0]['data']['current_user_messages']])

    async def test_new_input_during_startup_tail_is_explicit_continue(self):
        saved = asyncio.Event()
        self.service.subscribe(self.sid, lambda n, b: saved.set() if n == 'group_saved' else None)
        await self.service.send(self.sid, self.payload('原'), 'gaps'); await asyncio.wait_for(saved.wait(), 2)
        await self.service.close()
        resumed = CharacterGroupService(self.repo, FakeGroupTransport()); self.addAsyncCleanup(resumed.close)
        await resumed.start()
        await resumed.send(self.sid, self.payload('新输入授权继续'))
        await asyncio.wait_for(resumed.wait_idle(self.sid), 3)
        self.assertEqual(1, len(resumed.transport.calls))
        self.assertEqual(['新输入授权继续'], [m['content'] for m in resumed.transport.calls[0]['data']['current_user_messages']])

    async def test_private_ledger_and_candidate_never_enter_public_state_or_events(self):
        ai = next(p['instance_id'] for p in self.repo.load(self.sid)['participants'] if p['controller'] == 'ai')
        self.transport.value['ledger_ops'] = [{'op': 'add', 'kind': 'belief', 'content': 'PRIVATE-LEDGER',
            'source': {'type': 'model_inference', 'message_ids': ['b0'], 'evidence': [{'message_id': 'b0', 'quote': '甲'}]},
            'visibility': {'audience_instance_ids': [ai]}}]
        await self.service.send(self.sid, self.payload('输入'), 'gaps'); await self.idle()
        self.assertIn('PRIVATE-LEDGER', json.dumps(self.repo.load(self.sid)))
        self.assertNotIn('PRIVATE-LEDGER', json.dumps(self.service.view(self.sid)))
        self.assertNotIn('PRIVATE-LEDGER', json.dumps(self.events))
        for _, event in self.events:
            self.assertNotIn('ledger', event.get('state', {}))
            self.assertNotIn('messages', event.get('state', {}))

    async def test_whole_batch_regeneration_then_undo_uses_service_workers(self):
        await self.service.send(self.sid, self.payload('原输入')); await self.idle()
        old = self.repo.load(self.sid)['groups'][0]
        self.transport.value = result('重写甲', '重写乙')
        await self.service.batch(self.sid, {'client_action_id': str(uuid4()), 'expected_revision': self.repo.load(self.sid)['revision'],
                                          'operation': 'regenerate', 'target_group_id': old['group_id']}, 'instant')
        await self.idle()
        self.assertEqual('replaced', self.repo.load(self.sid)['groups'][0]['status'])
        self.assertEqual(['原输入', '重写甲', '重写乙'], [m['message']['content'] for m in self.service.view(self.sid)['messages']])
        new = self.repo.load(self.sid)['groups'][-1]
        await self.service.batch(self.sid, {'client_action_id': str(uuid4()), 'expected_revision': self.repo.load(self.sid)['revision'],
                                          'operation': 'undo', 'target_group_id': new['group_id']})
        self.assertEqual([], self.service.view(self.sid)['messages']); self.assertEqual(2, len(self.transport.calls))


if __name__ == '__main__': unittest.main()
