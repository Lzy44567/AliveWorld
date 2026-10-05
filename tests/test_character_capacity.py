import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.character_chat.capacity import capacity_report, pressure
from core.character_chat.models import create_session, CharacterSessionError, json_bytes
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat.service import CharacterChatService
from tests.test_character_chat_lifecycle import FakeTransport
from tests import test_character_chat_routes as route_fixtures


def fresh():
    return create_session(str(uuid4()), {'name': '容量合成', 'description': '固定资料'}, {'kind': 'character', 'key': '容量合成'})


def failed_action(attempts=1):
    return {'action_id': str(uuid4()), 'operation': 'send', 'fingerprint': 'a' * 64,
            'attempts': [{'request_id': str(uuid4()), 'base_revision': 0, 'status': 'failed'} for _ in range(attempts)]}


class CapacityPolicyTests(unittest.TestCase):
    def test_thresholds_exact_integer_comparison(self):
        for limit in (128, 512, 2048, 4096, 32768):
            near = (limit * 80 + 99) // 100
            self.assertEqual('normal', pressure(near - 1, limit))
            self.assertEqual('near', pressure(near, limit))
            self.assertEqual('at_limit', pressure(limit, limit))

    def test_public_counts_and_separate_operation_gates(self):
        value = fresh(); value['turns'] = [None] * 512
        report = capacity_report(value)
        self.assertEqual('blocked', report['operation_capacity']['send'])
        self.assertEqual('not_known_blocked', report['operation_capacity']['undo'])
        value['requests'] = [failed_action()] * 2048
        self.assertEqual({'blocked'}, set(capacity_report(value)['operation_capacity'].values()))
        value['requests'] = [failed_action(4096)]
        self.assertEqual({'blocked'}, set(capacity_report(value)['operation_capacity'].values()))

    def test_hidden_dimensions_combined_no_private_fields_or_extra_serialization(self):
        value = fresh(); value['ledger'] = [{'status': 'active', 'content': 'PRIVATE_SENTINEL'}] * 128
        report = capacity_report(value)
        self.assertEqual('at_limit', report['recording_pressure'])
        self.assertEqual({'not_known_blocked'}, set(report['operation_capacity'].values()))
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(report))
        self.assertEqual({'session_id', 'revision', 'version', 'public_counts', 'recording_pressure', 'operation_capacity'}, set(report))
        value['ledger'] = [{'status': 'superseded'}] * 2048
        self.assertEqual('at_limit', capacity_report(value)['recording_pressure'])

    def test_utf8_canonical_bytes_extensions_and_unknown_schema(self):
        value = fresh(); value['extensions']['test'] = '中文"\\' * 30
        raw = json_bytes(value); calls = []
        def encoded(item):
            calls.append(item); return json_bytes(item)
        with patch('core.character_chat.capacity.MAX_FILE_BYTES', len(raw)), patch('core.character_chat.capacity.json_bytes', side_effect=encoded):
            self.assertEqual('at_limit', capacity_report(value)['recording_pressure'])
        self.assertEqual(2, len(calls))  # One whole-session encoding plus bounded extensions.
        with patch('core.character_chat.capacity.MAX_EXTENSIONS_BYTES', len(json_bytes(value['extensions']))):
            self.assertEqual('at_limit', capacity_report(value)['recording_pressure'])
        value['schema_version'] = 2
        with self.assertRaises(CharacterSessionError) as error: capacity_report(value)
        self.assertEqual('SCHEMA_READ_ONLY', error.exception.code)


class CapacityRouteTests(unittest.TestCase):
    def setUp(self): route_fixtures.CharacterRouteTests.setUp(self)

    def test_get_whitelist_read_only_and_reject_extra_input(self):
        path = self.repo.directory / (self.sid + '.json')
        before = path.read_bytes(), path.stat().st_mtime_ns
        url = self.prefix + '/' + self.sid + '/capacity'
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, response.json()['public_counts']['formal_turns']['used'])
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))
        self.assertEqual(400, self.client.get(url + '?path=other').status_code)
        self.assertEqual(400, self.client.request('GET', url, json={'extra': True}).status_code)
        self.assertEqual(404, self.client.get(self.prefix + '/' + str(uuid4()) + '/capacity').status_code)

    def test_failed_attempt_same_revision_fresh_counts_no_cache(self):
        value = self.repo.load(self.sid)
        value['requests'] = [failed_action()]
        self.repo._write(value)
        url = self.prefix + '/' + self.sid + '/capacity'
        report = self.client.get(url).json()
        self.assertEqual(0, report['revision']); self.assertEqual(1, report['public_counts']['attempts']['used'])
        value['requests'][0]['attempts'].append(failed_action()['attempts'][0]); self.repo._write(value)
        report = self.client.get(url).json()
        self.assertEqual(0, report['revision']); self.assertEqual(2, report['public_counts']['attempts']['used'])

    def test_future_schema_and_corrupt_data_never_repaired(self):
        path = self.repo.directory / (self.sid + '.json')
        value = self.repo.load(self.sid); value['schema_version'] = 2
        path.write_bytes(json_bytes(value))
        before = path.read_bytes()
        response = self.client.get(self.prefix + '/' + self.sid + '/capacity')
        self.assertEqual('SCHEMA_READ_ONLY', response.json()['error']['code']); self.assertEqual(before, path.read_bytes())
        path.write_bytes(b'{bad')
        self.assertEqual('SESSION_CORRUPT', self.client.get(self.prefix + '/' + self.sid + '/capacity').json()['error']['code'])
        self.assertEqual(b'{bad', path.read_bytes())

    def test_action_attempt_hard_limits_zero_provider_and_drafts_preserved(self):
        for records in ([failed_action() for _ in range(2048)], [failed_action(4096)]):
            records[0]['retry_input'] = {'content': '失败草稿', 'mode': 'messenger', 'user_message_id': str(uuid4()), 'ai_message_id': str(uuid4())}
            value = self.repo.load(self.sid); value['requests'] = records; self.repo._write(value)
            for op in ('send', 'undo', 'regenerate'):
                payload = {'client_action_id': str(uuid4()), 'expected_revision': 0, 'operation': op, 'delivery': 'non_stream'}
                payload.update({'content': '应保留输入'} if op == 'send' else {'target_turn_id': str(uuid4())})
                response = self.client.post(self.prefix + '/' + self.sid + '/actions', json=payload)
                self.assertEqual('SESSION_LIMIT', response.json()['error']['code'])
            retry = self.client.post(self.prefix + '/' + self.sid + '/actions/' + records[0]['action_id'] + '/retry', json={
                'expected_revision': 0, 'retry_of': records[0]['attempts'][-1]['request_id'], 'retry_token': str(uuid4()), 'delivery': 'non_stream'})
            self.assertEqual('SESSION_LIMIT', retry.json()['error']['code'])
            self.assertEqual(0, self.transport.calls)
            self.assertEqual({'blocked'}, set(self.client.get(self.prefix + '/' + self.sid + '/capacity').json()['operation_capacity'].values()))


class CapacityLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_formal_512_blocks_send_not_legal_regenerate_or_undo(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = CharacterSessionRepository(Path(directory)); transport = FakeTransport(); service = CharacterChatService(repo, transport)
            value = repo.create(fresh()); sid = value['session_id']
            start = service.begin(sid, {'client_action_id': str(uuid4()), 'expected_revision': 0, 'operation': 'send', 'delivery': 'non_stream', 'content': '合成初轮'})
            await service.execute(start['job']['request_id'], lambda *_: None)
            value = repo.load(sid); turn, action = value['turns'][0], value['requests'][0]
            template = json.dumps([turn, action])
            ids = [turn['turn_id'], turn['action_id'], turn['request_id'], turn['user_message']['message_id'], turn['ai_message']['message_id']]
            value['turns'], value['requests'] = [], []
            for _ in range(512):
                raw = template
                for identity in ids: raw = raw.replace(identity, str(uuid4()))
                t, a = json.loads(raw); value['turns'].append(t); value['requests'].append(a)
            repo._write(value)
            calls = transport.calls
            with self.assertRaises(CharacterSessionError) as error:
                service.begin(sid, {'client_action_id': str(uuid4()), 'expected_revision': 1, 'operation': 'send', 'content': '超限', 'delivery': 'non_stream'})
            self.assertEqual('SESSION_LIMIT', error.exception.code); self.assertEqual(calls, transport.calls)
            for op in ('regenerate', 'undo'):
                current = repo.load(sid)
                start = service.begin(sid, {'client_action_id': str(uuid4()), 'expected_revision': current['revision'], 'operation': op, 'target_turn_id': current['turns'][-1]['turn_id'], 'delivery': 'non_stream'})
                if 'job' in start: await service.execute(start['job']['request_id'], lambda *_: None)
            self.assertEqual(511, len(repo.load(sid)['turns']))

    async def test_full_active_memory_empty_ops_can_commit_and_undo_is_not_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = CharacterSessionRepository(Path(directory)); transport = FakeTransport(); service = CharacterChatService(repo, transport)
            value = repo.create(fresh()); sid = value['session_id']
            async def send(content, operation='send'):
                value = repo.load(sid)
                payload = {'client_action_id': str(uuid4()), 'expected_revision': value['revision'], 'operation': operation, 'delivery': 'non_stream'}
                payload.update({'content': content} if operation == 'send' else {'target_turn_id': value['turns'][-1]['turn_id']})
                started = service.begin(sid, payload)
                if operation != 'undo': await service.execute(started['job']['request_id'], lambda *_: None)
                return started
            transport.with_ledger = True; await send('合成来源')
            value = repo.load(sid); template = value['ledger'][0]
            value['ledger'] = [{**copy.deepcopy(template), 'entry_id': str(uuid4())} for _ in range(128)]
            repo._write(value)
            self.assertEqual('at_limit', capacity_report(repo.load(sid))['recording_pressure'])
            transport.with_ledger = False; await send('没有账本更新也能回复')
            self.assertEqual(2, len(repo.load(sid)['turns']))
            transport.with_ledger = True; await send('超限新增应整轮失败')
            self.assertEqual(2, len(repo.load(sid)['turns']))
            before = capacity_report(repo.load(sid)); await send('', 'undo')
            after = capacity_report(repo.load(sid))
            self.assertEqual(1, after['public_counts']['formal_turns']['used'])
            self.assertGreater(after['public_counts']['actions']['used'], before['public_counts']['actions']['used'])
            self.assertEqual(128, len(repo.load(sid)['ledger']))
