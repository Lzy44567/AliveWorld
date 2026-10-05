import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.character_chat.memory import settings, units, select_memory, root_for, public_state
from core.character_chat.models import create_session, CharacterSessionError
from core.character_chat.context import build_context
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat.service import CharacterChatService
from tests.test_character_chat_lifecycle import FakeTransport


def fixture(count=40):
    session = create_session(str(uuid4()), {'name': '合成', 'description': '固定人设'}, {'kind': 'character', 'key': '合成'})
    ai = next(p['instance_id'] for p in session['participants'] if p['controller'] == 'ai')
    audience = [p['instance_id'] for p in session['participants']]
    for i in range(count):
        mid, tid = str(uuid4()), str(uuid4())
        content = '曾承诺一起去海边散步 Coffee tomorrow' if i == 0 else f'普通闲谈编号{i}'
        session['turns'].append({'turn_id': tid, 'user_message': {'message_id': mid, 'content': content, 'visibility': {'audience_instance_ids': audience}},
                                 'ai_message': {'message_id': str(uuid4()), 'content': '好的', 'visibility': {'audience_instance_ids': audience}}})
        session['ledger'].append({'entry_id': str(uuid4()), 'subject_instance_id': ai, 'kind': 'knowledge', 'content': content,
                                  'status': 'active', 'created_turn_id': tid, 'visibility': {'audience_instance_ids': audience},
                                  'source': {'type': 'player_statement', 'message_ids': [mid], 'evidence': [{'message_id': mid, 'quote': content}]}})
    return session


def pending(content):
    return {'content': content, 'mode': 'messenger', 'user_message_id': str(uuid4()), 'ai_message_id': str(uuid4())}


class MemoryPolicyTests(unittest.TestCase):
    def test_chinese_english_nfkc_whole_tokens_and_bounded_units(self):
        self.assertEqual(['海边', '边散', '散步', 'coffee', '12'], units('海边散步 ＣＯＦＦＥＥ 12 coffee'))
        self.assertEqual([], units('我'))
        self.assertLessEqual(len(units(' '.join(f't{i}' for i in range(200)))), 128)
        self.assertEqual(200, len(units(' '.join(f't{i}' for i in range(200)), limit=None)))
        value = fixture()
        for query in ('我们去海边吧', 'COFFEE', 'Tomorrow'):
            selected, _ = select_memory(value, query)
            self.assertEqual(value['ledger'][0]['entry_id'], selected[0]['entry_id'])
        selected, _ = select_memory(value, 'coffees')
        self.assertNotEqual(value['ledger'][0]['entry_id'], selected[0]['entry_id'])

    def test_protection_source_filter_privacy_and_no_mutation(self):
        value = fixture()
        root = value['ledger'][0]['entry_id']
        value['extensions']['character_memory'] = {'version': 1, 'important_entry_ids': [root]}
        private = value['ledger'][1]
        private['visibility']['audience_instance_ids'] = [private['subject_instance_id']]
        invalid = value['ledger'][2]
        invalid['source']['message_ids'] = [str(uuid4())]
        before = copy.deepcopy(value)
        selected, report = select_memory(value, private['content'])
        self.assertEqual(root, selected[0]['entry_id']); self.assertEqual(32, len(selected))
        self.assertIn(private, selected); self.assertNotIn(invalid, selected)
        self.assertNotIn(private['entry_id'], json.dumps(report)); self.assertNotIn(private['content'], json.dumps(report))
        self.assertEqual(value, before)

    def test_intents_and_final_budget_match_evidence_without_recalling_old_sources(self):
        value = fixture()
        root = value['ledger'][0]['entry_id']
        value['extensions']['character_memory'] = {'version': 1, 'important_entry_ids': [root]}
        for e in value['ledger'][1:13]:
            e['kind'] = 'intent'
        selected, _ = select_memory(value, '继续')
        self.assertLessEqual(sum(e['kind'] == 'intent' for e in selected), 8)
        with patch('core.character_chat.context.budget_report', side_effect=lambda _, raw, **kw: {'fits': not json.loads(raw)['ledger']}):
            plan, messages, ids, report = build_context(value, pending('海边'))
        self.assertEqual(set(), ids)
        self.assertEqual([], json.loads(plan.user_prompt)['ledger'])
        self.assertEqual('budget', next(e for e in report['memory_context']['entries'] if e['entry_id'] == root)['state'])
        self.assertNotIn(value['turns'][0]['user_message'], messages)
        with patch('core.character_chat.context.budget_report', return_value={'fits': False}):
            with self.assertRaises(CharacterSessionError):
                build_context(value, pending('继续'))

    def test_supersede_chain_cycles_invalid_identity_and_private_successor(self):
        value = fixture(2); old, new = value['ledger']
        value['extensions']['character_memory'] = {'version': 1, 'important_entry_ids': [old['entry_id']]}
        old['status'] = 'superseded'; new['supersedes_entry_id'] = old['entry_id']
        self.assertEqual(old['entry_id'], root_for(new, value))
        new['visibility']['audience_instance_ids'] = [new['subject_instance_id']]
        state = public_state(value)
        self.assertEqual([], state['protected_entries']); self.assertNotIn(new['entry_id'], json.dumps(state))
        old['supersedes_entry_id'] = new['entry_id']
        self.assertIsNone(root_for(new, value))
        del old['supersedes_entry_id']; new['kind'] = 'belief'
        self.assertIsNone(root_for(new, value))

    def test_settings_strict_missing_read_does_not_write(self):
        value = fixture(0); before = copy.deepcopy(value)
        self.assertEqual([], settings(value)['important_entry_ids']); self.assertEqual(before, value)
        for bad in ({'version': 2, 'important_entry_ids': []}, {'version': True, 'important_entry_ids': []}, {'version': 1, 'important_entry_ids': [1]}, {'version': 1, 'important_entry_ids': [], 'text': 'not allowed'}):
            value['extensions']['character_memory'] = bad
            with self.assertRaises((ValueError, TypeError, AttributeError)):
                settings(value)


class MemoryLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.repo = CharacterSessionRepository(Path(self.temp.name)); self.transport = FakeTransport(); self.transport.with_ledger = True
        self.service = CharacterChatService(self.repo, self.transport)
        self.sid = self.repo.create(create_session(str(uuid4()), {'name': '合成', 'description': '固定'}, {'kind': 'character', 'key': '合成'}))['session_id']

    async def send(self, content='合成记忆', operation='send'):
        value = self.repo.load(self.sid)
        payload = {'client_action_id': str(uuid4()), 'expected_revision': value['revision'], 'operation': operation, 'delivery': 'non_stream'}
        payload.update({'content': content} if operation == 'send' else {'target_turn_id': value['turns'][-1]['turn_id']})
        result = self.service.begin(self.sid, payload)
        return await self.service.execute(result['job']['request_id'], lambda *_: None) if 'job' in result else result['existing']

    def mark(self, eid, important=True, revision=None):
        return self.service.memory_mark(self.sid, self.repo.load(self.sid)['revision'] if revision is None else revision, eid, important)

    async def test_mark_reload_limit_noop_cas_and_atomic_failure(self):
        for i in range(9):
            await self.send(f'合成{i}')
        entries = self.repo.load(self.sid)['ledger']
        for e in entries[:8]: self.mark(e['entry_id'])
        revision = self.repo.load(self.sid)['revision']
        self.assertEqual(revision, self.mark(entries[0]['entry_id'])['revision'])
        with self.assertRaises(CharacterSessionError) as exc: self.mark(entries[8]['entry_id'])
        self.assertEqual('MEMORY_MARK_LIMIT', exc.exception.code)
        with self.assertRaises(CharacterSessionError) as exc: self.mark(entries[0]['entry_id'], False, 0)
        self.assertEqual('REVISION_CONFLICT', exc.exception.code)
        before = self.repo.load(self.sid)
        with patch('core.character_chat.repository.os.replace', side_effect=OSError('synthetic')):
            with self.assertRaises(CharacterSessionError): self.mark(entries[0]['entry_id'], False)
        self.assertEqual(before, self.repo.load(self.sid))
        self.mark(entries[0]['entry_id'], False); self.mark(entries[8]['entry_id'])
        self.assertEqual(8, len(settings(self.repo.load(self.sid))['important_entry_ids']))

    async def test_sources_supersede_undo_invalid_root_release_and_failure(self):
        await self.send('喜欢海边'); root = self.repo.load(self.sid)['ledger'][0]['entry_id']; self.mark(root)
        source = self.service.memory_sources(self.sid, root)
        self.assertEqual('喜欢海边', source['messages'][0]['content']); self.assertEqual({'entry_id', 'revision', 'messages'}, set(source))
        self.transport.supersede = True
        await self.send('更正为喜欢山林')
        value = self.repo.load(self.sid); active = [e for e in value['ledger'] if e['status'] == 'active'][0]
        self.assertEqual(root, root_for(active, value)); self.assertNotEqual(root, active['entry_id'])
        await self.send(operation='undo')
        self.assertEqual(root, public_state(self.repo.load(self.sid))['protected_entries'][0]['entry_id'])
        self.transport.raw = 'bad'; result = await self.send(operation='regenerate')
        self.assertEqual('failed', result['status']); self.assertEqual(root, public_state(self.repo.load(self.sid))['protected_entries'][0]['entry_id'])
        await self.send(operation='undo')
        self.assertEqual([root], public_state(self.repo.load(self.sid))['inactive_root_ids'])
        with self.assertRaises(CharacterSessionError): self.service.memory_sources(self.sid, root)
        self.mark(root, False); self.assertEqual([], settings(self.repo.load(self.sid))['important_entry_ids'])

    async def test_busy_private_cross_session_and_unknown_version_fail_closed(self):
        await self.send(); root = self.repo.load(self.sid)['ledger'][0]['entry_id']
        other = self.repo.create(create_session(str(uuid4()), {'name': '别的', 'description': '固定'}, {'kind': 'character', 'key': '别的'}))
        with self.assertRaises(CharacterSessionError): self.service.memory_sources(other['session_id'], root)
        begun = self.service.begin(self.sid, {'client_action_id': str(uuid4()), 'expected_revision': 1, 'operation': 'send', 'content': '等待'})
        with self.assertRaises(CharacterSessionError) as exc: self.mark(root)
        self.assertEqual('SESSION_BUSY', exc.exception.code)
        await self.service.execute(begun['job']['request_id'], lambda *_: None)
        value = self.repo.load(self.sid); value['ledger'][0]['visibility']['audience_instance_ids'] = [value['ledger'][0]['subject_instance_id']]
        revision = value['revision']; value['revision'] += 1
        self.repo.save(value, expected_revision=revision)
        with self.assertRaises(CharacterSessionError): self.mark(root)
        with self.assertRaises(CharacterSessionError): self.service.memory_sources(self.sid, root)
        value = self.repo.load(self.sid); value['extensions']['character_memory'] = {'version': 2, 'important_entry_ids': []}
        revision = value['revision']; value['revision'] += 1
        with self.assertRaises(CharacterSessionError): self.repo.save(value, expected_revision=revision)

    async def test_old_topic_recall_exact_request_report_and_evidence_set(self):
        await self.send('喜欢海边散步')
        root = self.repo.load(self.sid)['ledger'][0]['entry_id']; self.mark(root)
        for i in range(34): await self.send(f'普通闲谈编号{i}')
        result = await self.send('我们去海边吧')
        data = json.loads(self.transport.plans[-1].user_prompt)
        self.assertEqual(root, data['ledger'][0]['entry_id'])
        self.assertNotIn('喜欢海边散步', [m['content'] for m in data['history']])
        self.assertEqual('sent', next(e for e in result['memory_context_report']['entries'] if e['entry_id'] == root)['state'])
        self.assertEqual(36, self.transport.calls)

    async def test_old_ledger_quote_does_not_expand_allowed_evidence(self):
        await self.send('旧来源只在账本里')
        root_entry = self.repo.load(self.sid)['ledger'][0]; self.mark(root_entry['entry_id'])
        self.transport.with_ledger = False
        for i in range(21): await self.send(f'新回合{i}')
        old_mid = root_entry['source']['message_ids'][0]
        self.transport.raw = json.dumps({'reply': '不能伪造经历', 'ledger_ops': [{'op': 'add', 'kind': 'experience', 'content': '非法重新包装旧事实',
            'source': {'type': 'dialogue_event', 'message_ids': [old_mid], 'evidence': [{'message_id': old_mid, 'quote': '旧来源只在账本里'}]},
            'visibility': root_entry['visibility']}]}, ensure_ascii=False)
        before = self.repo.load(self.sid)
        result = await self.send('旧来源')
        self.assertEqual('failed', result['status']); self.assertEqual('CONTRACT_INVALID', result['error_code'])
        after = self.repo.load(self.sid)
        self.assertEqual(before['turns'], after['turns']); self.assertEqual(before['ledger'], after['ledger'])
