import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.character_chat.models import create_session, CharacterSessionError
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat.service import CharacterChatService
from core.character_chat.group_migration import convert_legacy_session
from core.character_chat.group_schema import validate_schema2
from core.character_chat.group_service import CharacterGroupService
from core.character_chat.group_lifecycle import accept_input, batch_action
from core.character_chat.legacy_lifecycle import begin_legacy_retry, commit_legacy, fail_legacy
from core.character_chat.legacy_context import build_legacy_retry_context
from core.character_chat.group_records import formal_messages, capacity_groups
from core.character_chat.protocol import V1, V2, V3
from core.character_chat.context_contract import LEGACY, M3, C3
from tests.test_character_chat_lifecycle import FakeTransport
from tests.test_character_multibubble_protocol import result


class LegacyExecutionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        old_repo = CharacterSessionRepository(Path(self.temp.name) / 'old')
        old = old_repo.create(create_session(str(uuid4()), {'name': '合成', 'description': '固定'},
                                            {'kind': 'character', 'key': '合成'}))
        old_service = CharacterChatService(old_repo, FakeTransport())
        old_service.begin(old['session_id'], {'client_action_id': str(uuid4()), 'expected_revision': 0,
                                            'operation': 'send', 'content': '旧输入'})
        self.value = convert_legacy_session(old_repo.load(old['session_id']))
        self.action = self.value['requests'][0]
        self.original = copy.deepcopy(self.action.get('legacy_retry_snapshot') or self.action['attempts'][0]['legacy_retry_snapshot'])
        self.repo = CharacterSessionRepository(Path(self.temp.name) / 'new', validator=validate_schema2, supported_schemas=(2,))
        self.repo.create(self.value); self.sid = self.value['session_id']
        self.transport = FakeTransport()
        self.service = CharacterGroupService(self.repo, self.transport)
        self.addAsyncCleanup(self.service.close)
        self.events = []
        self.service.subscribe(self.sid, lambda name, body: self.events.append((name, body)))

    def begin(self, value=None):
        value = self.value if value is None else value
        action = value['requests'][0]
        attempt, _ = begin_legacy_retry(value, action['action_id'], action['attempts'][-1]['request_id'], str(uuid4()))
        validate_schema2(value)
        return attempt

    async def retry(self, token=None):
        value = self.repo.load(self.sid); action = value['requests'][0]
        payload = {'expected_revision': value['revision'], 'retry_of': action['attempts'][-1]['request_id'], 'retry_token': token or str(uuid4())}
        return await self.service.retry(self.sid, action['action_id'], payload), payload

    async def idle(self):
        await asyncio.wait_for(self.service.wait_idle(self.sid), 3)

    def test_six_protocols_commit_original_ids_only_after_success(self):
        for protocol in (V1, V2):
            for context in (LEGACY, M3, C3):
                with self.subTest(protocol=protocol, context=context):
                    value = copy.deepcopy(self.value); old = value['requests'][0]['attempts'][0]
                    old.update(reply_contract_id=protocol, context_contract_id=context)
                    for snapshot in (old['legacy_retry_snapshot'], value['requests'][0].get('legacy_retry_snapshot', {})):
                        if not snapshot: continue
                        snapshot.update(reply_contract_id=protocol, context_contract_id=context)
                        if context == C3: snapshot['ooc_note'] = '场外'
                    attempt = self.begin(value)
                    self.assertEqual({}, formal_messages(value)); self.assertEqual([], value['groups'])
                    _, evidence, entries, _ = build_legacy_retry_context(value, value['requests'][0], attempt)
                    body = {'reply': '原协议回复', 'ledger_ops': []}
                    if protocol == V2: body['memory_annotations'] = []
                    group = commit_legacy(value, attempt['request_id'], json.dumps(body), evidence, entries)
                    validate_schema2(value)
                    self.assertEqual([self.original['user_message_id']], group['input_ids'])
                    self.assertEqual(self.original['ai_message_id'], group['bubbles'][0]['message']['message_id'])
                    self.assertNotIn('legacy_retry_snapshot', value['requests'][0])
                    self.assertEqual(2, len(formal_messages(value)))

    def test_fail_cancel_retry_and_recover_keep_snapshot_nonformal(self):
        for status in ('failed', 'cancelled', 'interrupted'):
            attempt = self.begin()
            self.assertTrue(fail_legacy(self.value, attempt['request_id'], status))
            validate_schema2(self.value)
            self.assertEqual(self.original, self.value['requests'][0]['legacy_retry_snapshot'])
            self.assertEqual({}, formal_messages(self.value))
        self.assertEqual(4, len(self.value['requests'][0]['attempts']))

    def test_strict_execution_and_identity_corruption_rejected(self):
        self.begin()
        changes = [lambda v: v['requests'][0]['attempts'][-1]['legacy_execution'].update(context_epoch=1),
                   lambda v: v['requests'][0]['attempts'][-1]['legacy_execution'].update(extra=True),
                   lambda v: v['requests'][0]['attempts'][-1].update(context_contract_id=LEGACY),
                   lambda v: v['requests'][0]['attempts'][-1]['legacy_execution'].update(group_id=v['participants'][0]['instance_id']),
                   lambda v: v['requests'][0]['legacy_retry_snapshot'].update(ai_message_id=v['requests'][0]['legacy_retry_snapshot']['user_message_id'])]
        for change in changes:
            value = copy.deepcopy(self.value); change(value)
            with self.subTest(change=change), self.assertRaises(CharacterSessionError): validate_schema2(value)

    def test_new_formal_input_blocks_stale_retry_and_pending_send_is_busy(self):
        value = copy.deepcopy(self.value)
        accept_input(value, {'client_action_id': str(uuid4()), 'expected_revision': value['revision'], 'content': '新输入'})
        with self.assertRaises(CharacterSessionError) as caught: self.begin(value)
        self.assertEqual('STALE_RETRY', caught.exception.code)
        self.begin()
        before = copy.deepcopy(self.value)
        with self.assertRaises(CharacterSessionError) as caught:
            accept_input(self.value, {'client_action_id': str(uuid4()), 'expected_revision': self.value['revision'], 'content': '新输入'})
        self.assertEqual('SESSION_BUSY', caught.exception.code); self.assertEqual(before, self.value)
        self.assertEqual(1, len(capacity_groups(self.value)))

    async def test_service_stream_single_preview_commit_and_token_replay_no_call(self):
        attempt, payload = await self.retry(); await self.idle()
        value = self.repo.load(self.sid)
        self.assertEqual('committed', value['requests'][0]['attempts'][-1]['status'])
        self.assertEqual(1, self.transport.calls)
        self.assertEqual(1, sum(n == 'preview_start' for n, _ in self.events))
        self.assertEqual(1, sum(n == 'preview_end' for n, _ in self.events))
        self.assertEqual(1, sum(n == 'group_saved' for n, _ in self.events))
        await self.service.retry(self.sid, self.action['action_id'], payload); await self.idle()
        self.assertEqual(1, self.transport.calls)
        self.assertEqual(self.original['ai_message_id'], self.service.view(self.sid)['messages'][-1]['message']['message_id'])

    async def test_provider_failure_and_restart_do_not_create_messages_or_charge(self):
        self.transport.raw = 'bad JSON'
        await self.retry(); await self.idle()
        self.assertEqual([], self.service.view(self.sid)['messages'])
        self.assertFalse(any(n == 'group_saved' for n, _ in self.events))
        self.assertEqual('failed', self.repo.load(self.sid)['requests'][0]['attempts'][-1]['status'])
        value = self.repo.load(self.sid)
        self.begin(value)
        def replace(current):
            current.clear(); current.update(value); return None, True
        self.repo.transaction(self.sid, replace)
        await self.service.start()
        self.assertEqual('interrupted', self.repo.load(self.sid)['requests'][0]['attempts'][-1]['status'])
        self.assertEqual(1, self.transport.calls); self.assertEqual([], self.service.view(self.sid)['messages'])

    async def test_cancel_before_provider_zero_calls_then_immediate_retry(self):
        def cancel(name, body):
            if name == 'accepted':
                self.service.cancel(self.sid, body['request_id'])
        detach = self.service.subscribe(self.sid, cancel)
        await self.retry(); await self.idle(); detach()
        self.assertEqual(0, self.transport.calls)
        await self.retry(); await self.idle()
        self.assertEqual(1, self.transport.calls)
        self.assertEqual(2, len(self.service.view(self.sid)['messages']))

    async def test_persistence_failure_no_saved_broadcast_and_no_formal_input(self):
        original_write = self.repo._write
        def reject(value):
            if value.get('groups'): raise CharacterSessionError('PERSISTENCE_FAILED')
            return original_write(value)
        with patch.object(self.repo, '_write', side_effect=reject):
            await self.retry(); await self.idle()
        self.assertEqual([], self.repo.load(self.sid)['groups'])
        self.assertEqual([], self.repo.load(self.sid)['inputs'])
        self.assertFalse(any(n == 'group_saved' for n, _ in self.events))

    async def test_next_normal_send_v3_and_batch_undo_preserves_archive_ids(self):
        await self.retry(); await self.idle()
        value = self.repo.load(self.sid); target = value['groups'][0]
        batch_action(value, {'client_action_id': str(uuid4()), 'expected_revision': value['revision'],
                             'operation': 'undo', 'target_group_id': target['group_id']})
        validate_schema2(value); self.assertEqual({}, formal_messages(value))
        self.assertEqual(self.original['ai_message_id'], value['groups'][0]['bubbles'][0]['message']['message_id'])
        self.transport.raw = json.dumps(result('新甲', '新乙'))
        await self.service.send(self.sid, {'client_action_id': str(uuid4()), 'expected_revision': self.repo.load(self.sid)['revision'], 'content': '新请求'})
        await self.idle()
        self.assertEqual(V3, self.transport.plans[-1].contract_id)

    async def test_old_regeneration_failure_keeps_target_success_replaces_atomically(self):
        old_repo = CharacterSessionRepository(Path(self.temp.name) / 'regen')
        old = old_repo.create(create_session(str(uuid4()), {'name': '合成', 'description': '固定'},
                                            {'kind': 'character', 'key': '合成'}))
        transport = FakeTransport(); transport.with_ledger = True
        service = CharacterChatService(old_repo, transport)
        sid = old['session_id']
        begun = service.begin(sid, {'client_action_id': str(uuid4()), 'expected_revision': 0, 'operation': 'send', 'content': '旧输入'})
        await service.execute(begun['job']['request_id'], lambda *_: None)
        old = old_repo.load(sid)
        service.begin(sid, {'client_action_id': str(uuid4()), 'expected_revision': old['revision'],
                            'operation': 'regenerate', 'target_turn_id': old['turns'][-1]['turn_id']})
        value = convert_legacy_session(old_repo.load(sid)); action = value['requests'][-1]
        target = copy.deepcopy(value['groups'][0]); ledger = copy.deepcopy(value['ledger'])
        snapshot = action.get('legacy_retry_snapshot') or action['attempts'][-1]['legacy_retry_snapshot']
        attempt, _ = begin_legacy_retry(value, action['action_id'], action['attempts'][-1]['request_id'], str(uuid4()))
        fail_legacy(value, attempt['request_id'])
        self.assertEqual(target, value['groups'][0]); self.assertEqual(ledger, value['ledger'])
        attempt, _ = begin_legacy_retry(value, action['action_id'], attempt['request_id'], str(uuid4()))
        _, evidence, entries, _ = build_legacy_retry_context(value, action, attempt)
        self.assertEqual([], evidence)
        before = copy.deepcopy(value)
        with self.assertRaises(CharacterSessionError): commit_legacy(value, attempt['request_id'], 'bad', evidence, entries)
        self.assertEqual(before, value)
        group = commit_legacy(value, attempt['request_id'], json.dumps({'reply': '新分支', 'ledger_ops': [], 'memory_annotations': []}), evidence, entries)
        validate_schema2(value)
        self.assertEqual('replaced', value['groups'][0]['status']); self.assertEqual([], value['ledger'])
        self.assertEqual([snapshot['user_message_id']], group['input_ids'])
        self.assertEqual({snapshot['user_message_id'], snapshot['ai_message_id']}, set(formal_messages(value)))
        batch_action(value, {'client_action_id': str(uuid4()), 'expected_revision': value['revision'],
                            'operation': 'undo', 'target_group_id': group['group_id']})
        validate_schema2(value); self.assertEqual({}, formal_messages(value))

    async def test_sourced_highlight_notice_and_undo(self):
        pending = self.original
        audience = [p['instance_id'] for p in self.value['participants']]
        op = {'op': 'add', 'kind': 'experience', 'content': '建立承诺',
              'source': {'type': 'dialogue_event', 'message_ids': [pending['ai_message_id']],
                         'evidence': [{'message_id': pending['ai_message_id'], 'quote': '承诺'}]},
              'visibility': {'audience_instance_ids': audience}}
        self.transport.raw = json.dumps({'reply': '这是承诺', 'ledger_ops': [op],
                                         'memory_annotations': [{'op_index': 0, 'reason': 'relationship_turn'}]})
        await self.retry(); await self.idle()
        value = self.repo.load(self.sid); group = value['groups'][0]
        self.assertEqual([value['ledger'][0]['entry_id']], group['memory_notice']['entry_ids'])
        self.assertEqual([pending['ai_message_id']], value['ledger'][0]['source']['message_ids'])
        batch_action(value, {'client_action_id': str(uuid4()), 'expected_revision': value['revision'],
                            'operation': 'undo', 'target_group_id': group['group_id']})
        validate_schema2(value); self.assertEqual([], value['ledger'])

    async def test_legacy_real_connection_tiny_budget_zero_calls(self):
        with patch.object(self.transport, 'snapshot', return_value={'budget_options': {'context_window': 100, 'output_reserve': 50}}):
            await self.retry(); await self.idle()
        self.assertEqual(0, self.transport.calls)
        self.assertEqual([], self.service.view(self.sid)['messages'])
