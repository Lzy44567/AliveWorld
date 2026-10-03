import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.v1 import character_chat_routes as routes
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat.service import CharacterChatService
from tests.test_character_chat_lifecycle import FakeTransport


class CharacterRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = CharacterSessionRepository(Path(self.temp.name) / 'sessions')
        self.transport = FakeTransport()
        self.service = CharacterChatService(self.repo, self.transport)
        self.repo_patch = patch.object(routes, 'repository', self.repo)
        self.service_patch = patch.object(routes, 'service', self.service)
        self.repo_patch.start()
        self.service_patch.start()
        self.addCleanup(self.repo_patch.stop)
        self.addCleanup(self.service_patch.stop)
        self.asset_patch = patch.object(routes, 'load_asset', return_value={'name': '合成', 'description': '固定资料',
            '_external_import': {'source': {'private': 'PRIVATE_EXTENSION_SYNTHETIC'}}})
        self.asset = self.asset_patch.start()
        self.addCleanup(self.asset_patch.stop)
        app = FastAPI()
        app.include_router(routes.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.prefix = '/api/v1/character-sessions'
        self.create_payload = {'client_creation_id': str(uuid4()), 'ai_asset_ref': {'kind': 'character', 'key': '合成'},
                               'presentation_mode': 'messenger'}
        response = self.client.post(self.prefix, json=self.create_payload)
        self.assertEqual(201, response.status_code, response.text)
        self.sid = response.json()['session_id']

    def test_creation_duplicate_before_asset_reads_and_tombstone_replay(self):
        self.asset.reset_mock()
        duplicate = self.client.post(self.prefix, json=self.create_payload)
        self.assertEqual(201, duplicate.status_code)
        self.asset.assert_not_called()
        self.assertNotIn('PRIVATE_EXTENSION_SYNTHETIC', duplicate.text)
        deleted = self.client.request('DELETE', self.prefix + '/' + self.sid, json={'expected_revision': 0})
        self.assertEqual(204, deleted.status_code)
        replay = self.client.post(self.prefix, json=self.create_payload)
        self.assertEqual(410, replay.status_code)
        self.asset.assert_not_called()
        self.assertEqual(410, self.client.get(self.prefix + '/' + self.sid).status_code)
        self.assertEqual(204, self.client.request('DELETE', self.prefix + '/' + self.sid, json={'expected_revision': 0}).status_code)

    def test_strict_request_and_metadata_readonly_projection(self):
        url = self.prefix + '/' + self.sid
        for payload in ({'expected_revision': True, 'title': 'hi'}, {'expected_revision': 0, 'unknown': 'x'},
                        {'expected_revision': 0, 'presentation_mode': ['bad']}):
            self.assertEqual(400, self.client.patch(url, json=payload).status_code)
        self.assertEqual(400, self.client.patch(url, content='{"expected_revision":0,"title":"a","title":"b"}',
            headers={'Content-Type': 'application/json'}).status_code)
        changed = self.client.patch(url, json={'expected_revision': 0, 'presentation_mode': 'roleplay'})
        self.assertEqual(200, changed.status_code)
        self.assertEqual(1, changed.json()['revision'])
        self.assertNotIn('PRIVATE_EXTENSION', changed.text)
        listing = self.client.get(self.prefix).json()
        self.assertEqual(self.sid, listing['sessions'][0]['session_id'])
        self.assertNotIn('turns', listing['sessions'][0])

    def test_nonstream_send_history_undo_status(self):
        url = self.prefix + '/' + self.sid
        aid = str(uuid4())
        result = self.client.post(url + '/actions', json={'client_action_id': aid, 'expected_revision': 0,
            'operation': 'send', 'content': '合成输入', 'delivery': 'non_stream'})
        self.assertEqual(200, result.status_code, result.text)
        data = result.json()
        self.assertEqual('committed', data['status'])
        self.assertNotIn('ledger_inverse', result.text)
        turns = self.client.get(url + '/turns').json()['turns']
        self.assertEqual(data['turn_id'], turns[0]['turn_id'])
        undo = self.client.post(url + '/actions', json={'client_action_id': str(uuid4()), 'expected_revision': 1,
            'operation': 'undo', 'target_turn_id': data['turn_id']})
        self.assertEqual('committed', undo.json()['status'])
        status = self.client.get(url + '/actions/' + aid).json()
        self.assertEqual('withdrawn', status['result_state'])
        self.assertNotIn('turn', status)
        self.assertEqual([], self.client.get(url).json()['turns'])

    def test_summary_projection_formal_time_privacy_and_undo(self):
        url = self.prefix + '/' + self.sid
        self.client.post(url + '/actions', json={'client_action_id': str(uuid4()), 'expected_revision': 0,
            'operation': 'send', 'content': '合成输入', 'delivery': 'non_stream'})
        stored = self.repo.load(self.sid)
        stored['updated_at'] = '2099-01-01T00:00:00Z'
        stored['turns'][-1]['ai_message']['content'] = '中文😀 ' * 200
        from core.character_chat.service import session_summary
        summary = session_summary(stored)
        self.assertEqual(stored['turns'][-1]['created_at'], summary['last_activity_at'])
        self.assertEqual(160, len(summary['last_message_preview']))
        self.assertEqual(1, summary['latest_ai_committed_revision'])
        self.assertEqual({'session_id', 'title', 'revision', 'presentation_mode', 'created_at', 'ai_name',
            'last_activity_at', 'last_message_preview', 'latest_ai_message_id', 'latest_ai_committed_revision', 'pending'}, set(summary))
        response = self.client.get(self.prefix + '?view=summary')
        self.assertNotIn('participants', response.text)
        self.assertNotIn('PRIVATE_EXTENSION_SYNTHETIC', response.text)
        self.assertEqual(400, self.client.get(self.prefix + '?view=invalid').status_code)
        self.client.post(url + '/actions', json={'client_action_id': str(uuid4()), 'expected_revision': 1,
            'operation': 'undo', 'target_turn_id': stored['turns'][-1]['turn_id']})
        empty = self.client.get(self.prefix + '?view=summary').json()['sessions'][0]
        self.assertIsNone(empty['latest_ai_message_id'])
        self.assertEqual('', empty['last_message_preview'])

    def test_summary_census_more_than_fifty_sessions(self):
        for n in range(51):
            payload = {**self.create_payload, 'client_creation_id': str(uuid4()), 'title': f'合成{n}'}
            self.assertEqual(201, self.client.post(self.prefix, json=payload).status_code)
        first = self.client.get(self.prefix + '?view=summary').json()
        second = self.client.get(self.prefix + '?view=summary&cursor=' + first['next_cursor']).json()
        self.assertEqual(50, len(first['sessions']))
        self.assertEqual(2, len(second['sessions']))
        self.assertIsNone(second['next_cursor'])
        self.assertEqual(52, len({r['session_id'] for r in first['sessions'] + second['sessions']}))

    def test_sse_versioned_terminal_and_private_ledger_opt_in(self):
        self.transport.with_ledger = True
        url = self.prefix + '/' + self.sid
        response = self.client.post(url + '/actions', json={'client_action_id': str(uuid4()), 'expected_revision': 0,
            'operation': 'send', 'content': '合成陈述', 'delivery': 'stream'})
        self.assertEqual(200, response.status_code)
        self.assertEqual('text/event-stream; charset=utf-8', response.headers['content-type'])
        frames = response.text.split('\n\n')
        names, seq = [], []
        for frame in frames:
            if not frame.startswith('event: '):
                continue
            name, payload = frame.split('\ndata: ')
            value = json.loads(payload)
            names.append(name[7:])
            seq.append(value['seq'])
            self.assertEqual(1, value['v'])
            self.assertEqual(self.sid, value['session_id'])
        self.assertEqual(['accepted', 'reply_delta', 'validating', 'committed'], names)
        self.assertEqual([1, 2, 3, 4], seq)
        self.assertNotIn('ledger_inverse', response.text)

    def test_corrupt_runtime_records_fail_closed_before_metadata(self):
        path = self.repo.directory / (self.sid + '.json')
        value = json.loads(path.read_text(encoding='utf-8'))
        value['requests'] = [{'action_id': str(uuid4()), 'operation': 'send', 'attempts': []}]
        path.write_text(json.dumps(value), encoding='utf-8')
        before = path.read_bytes()
        response = self.client.patch(self.prefix + '/' + self.sid, json={'expected_revision': 0, 'title': '不应修改'})
        self.assertEqual(500, response.status_code)
        self.assertEqual('SESSION_CORRUPT', response.json()['error']['code'])
        self.assertEqual(before, path.read_bytes())
