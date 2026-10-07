import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from core.character_chat.group_migration import convert_legacy_session
from core.character_chat.group_records import formal_messages, conversation_projection, pending_inputs, unread_messages
from core.character_chat.group_schema import validate_schema2
from core.character_chat.models import CharacterSessionError, create_session, validate_session
from core.character_chat.memory import formal_messages as legacy_formal_messages
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat.service import CharacterChatService
from tests.test_character_chat_lifecycle import FakeTransport


class GroupStorageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = CharacterSessionRepository(Path(self.temp.name))
        self.transport = FakeTransport()
        self.service = CharacterChatService(self.repo, self.transport)
        self.session = self.repo.create(create_session(str(uuid4()), {'name': '合成', 'description': '人设'},
                                                       {'kind': 'character', 'key': '合成'}))
        self.sid = self.session['session_id']

    async def send(self, operation='send', content='测试台词', ooc=None):
        old = self.repo.load(self.sid)
        payload = {'client_action_id': str(uuid4()), 'expected_revision': old['revision'], 'operation': operation}
        if operation == 'send':
            payload['content'] = content
            if ooc:
                payload['ooc_note'] = ooc
        else:
            payload['target_turn_id'] = old['turns'][-1]['turn_id']
        begun = self.service.begin(self.sid, payload)
        if 'job' in begun:
            await self.service.execute(begun['job']['request_id'], lambda *_: None)
        return self.repo.load(self.sid)

    def assert_identity_preserved(self, original, converted):
        self.assertEqual(original['ledger'], converted['ledger'])
        old = legacy_formal_messages(original)
        new = formal_messages(converted)
        self.assertEqual(set(old), set(new))
        for mid, message in old.items():
            comparison = dict(new[mid]); comparison.pop('seq')
            self.assertEqual(message, comparison)
        for key in ('session_id', 'participants', 'opening', 'world_binding', 'extensions', 'revision'):
            self.assertEqual(original.get(key), converted.get(key))
        self.assertEqual([], unread_messages(converted))
        self.assertEqual([], pending_inputs(converted))

    async def test_pure_deterministic_conversion_no_repository_or_source_write(self):
        original = await self.send(ooc='这句是场外')
        original = await self.send(content='第二句')
        path = Path(self.temp.name) / f'{self.sid}.json'
        raw, modified = path.read_bytes(), path.stat().st_mtime_ns
        before = copy.deepcopy(original)
        converted = convert_legacy_session(original)
        self.assertEqual(before, original)
        self.assertEqual(converted, convert_legacy_session(original))
        self.assertEqual(converted, convert_legacy_session(converted))
        self.assertEqual(raw, path.read_bytes())
        self.assertEqual(modified, path.stat().st_mtime_ns)
        self.assert_identity_preserved(original, converted)
        self.assertNotIn('turns', converted)
        self.assertEqual('这句是场外', conversation_projection(converted)[0]['ooc_note'])
        self.assertNotIn('ooc_note', formal_messages(converted)[converted['inputs'][0]['input_id']])

    async def test_multiple_regeneration_and_undo_keep_archives_out_of_sources(self):
        original = await self.send()
        original = await self.send('regenerate')
        original = await self.send('regenerate')
        converted = convert_legacy_session(original)
        self.assert_identity_preserved(original, converted)
        self.assertEqual(3, len(converted['groups']))
        self.assertEqual(2, sum(g['status'] == 'replaced' for g in converted['groups']))
        original = await self.send('undo')
        converted = convert_legacy_session(original)
        self.assert_identity_preserved(original, converted)
        self.assertEqual([], conversation_projection(converted))
        self.assertEqual(3, len(converted['groups']))

    async def test_pending_is_interrupted_not_formal_input_or_v3(self):
        old = self.repo.load(self.sid)
        payload = {'client_action_id': str(uuid4()), 'expected_revision': 0, 'operation': 'send',
                   'content': '还没保存的旧输入', 'ooc_note': '旧场外'}
        begun = self.service.begin(self.sid, payload)
        original = self.repo.load(self.sid)
        converted = convert_legacy_session(original)
        self.assertEqual([], converted['inputs'])
        self.assertEqual([], converted['groups'])
        attempt = converted['requests'][0]['attempts'][0]
        self.assertEqual('interrupted', attempt['status'])
        self.assertEqual('character.reply.v2', attempt['reply_contract_id'])
        self.assertEqual('旧场外', attempt['legacy_retry_snapshot']['ooc_note'])
        self.assertEqual('pending', original['requests'][0]['attempts'][0]['status'])
        self.assertEqual(0, self.transport.calls)
        self.service.cancel(self.sid, begun['job']['request_id'])
        await self.service.execute(begun['job']['request_id'], lambda *_: None)

    async def test_unknown_and_old_reader_fail_closed_no_implicit_new_writes(self):
        converted = convert_legacy_session(self.session)
        with self.assertRaises(CharacterSessionError) as caught:
            validate_session(converted)
        self.assertEqual('SCHEMA_READ_ONLY', caught.exception.code)
        future = dict(converted, schema_version=3)
        with self.assertRaises(CharacterSessionError):
            convert_legacy_session(future)
        self.assertEqual(1, self.repo.load(self.sid)['schema_version'])

    async def test_corruption_identity_sequence_visibility_and_candidates_rejected(self):
        converted = convert_legacy_session(await self.send())
        bad = []
        value = copy.deepcopy(converted); value['inputs'][0]['message']['seq'] = value['groups'][0]['bubbles'][0]['message']['seq']; bad.append(value)
        value = copy.deepcopy(converted); value['read_ai_seq'] = value['next_seq']; bad.append(value)
        value = copy.deepcopy(converted); value['groups'][0]['delivered_count'] = 0; bad.append(value)
        value = copy.deepcopy(converted); value['groups'][0]['bubbles'][0]['message']['message_id'] = value['inputs'][0]['input_id']; bad.append(value)
        value = copy.deepcopy(converted); value['inputs'][0]['message']['visibility']['audience_instance_ids'] *= 2; bad.append(value)
        value = copy.deepcopy(converted); value['groups'][0]['input_ids'] *= 2; bad.append(value)
        value = copy.deepcopy(converted); value['turns'] = []; bad.append(value)
        for value in bad:
            with self.subTest(value=str(value)[:100]), self.assertRaises(CharacterSessionError):
                validate_schema2(value)


if __name__ == '__main__':
    unittest.main()
