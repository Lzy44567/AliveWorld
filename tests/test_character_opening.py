"""Synthetic B1 contracts; no player data or real provider calls."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.character_chat.models import CharacterSessionError, create_session, validate_session
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat.context import build_context
from core.character_chat.service import CharacterChatService, session_summary, session_view
from tests.test_character_chat_lifecycle import FakeTransport
from tests import test_character_chat_routes as route_fixture


def candidate(opening='预置：玩家已经承诺，{{user}} <script>not executable</script>', **kwargs):
    return create_session(str(uuid4()), {'name': '合成角色', 'description': '固定人设'},
                          {'kind': 'character', 'key': '合成'}, opening_text=opening, **kwargs)


class OpeningStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = CharacterSessionRepository(Path(self.temp.name))

    def test_empty_legacy_fingerprint_and_no_read_writeback(self):
        cid = str(uuid4())
        make = lambda **kw: create_session(cid, {'name': '合成', 'description': '固定'}, {'kind': 'character', 'key': '合成'}, **kw)
        base = make()
        for content in ('', ' \n\t '):
            other = make(opening_text=content)
            self.assertNotIn('opening', other)
            self.assertEqual(base['creation_fingerprint'], other['creation_fingerprint'])
        saved = self.repo.create(base)
        path = self.repo._path(saved['session_id'])
        before = hashlib.sha256(path.read_bytes()).digest()
        session_view(self.repo.load(saved['session_id']))
        self.assertEqual(before, hashlib.sha256(path.read_bytes()).digest())
        self.assertIsNone(session_summary(saved)['last_message_kind'])

    def test_unicode_boundaries_and_strict_types(self):
        value = candidate('😀' * 8000)
        self.repo.create(value)
        for content in ('😀' * 8001, None, 0, False, [], {}):
            with self.subTest(content_type=type(content).__name__), self.assertRaises(CharacterSessionError):
                candidate(content)
        self.assertEqual([], value['turns'])
        self.assertEqual([], value['ledger'])
        self.assertEqual([], value['requests'])
        self.assertEqual(0, value['revision'])

    def test_bad_opening_data_fail_closed(self):
        value = candidate()
        ai = next(p for p in value['participants'] if p['controller'] == 'ai')
        changes = ({'version': True}, {'version': 2}, {'extra': 'no'}, {'content': ' '}, {'content': None},
                   {'opening_id': ai['instance_id']}, {'opening_id': 'invalid'}, {'created_at': 'other'},
                   {'speaker_instance_id': value['participants'][0]['instance_id']}, {'source_type': 'player_statement'})
        for change in changes:
            bad = copy.deepcopy(value); bad['opening'].update(change)
            with self.subTest(change=change), self.assertRaises(CharacterSessionError):
                validate_session(bad)
        saved = self.repo.create(value)
        path = self.repo._path(saved['session_id'])
        bad = copy.deepcopy(saved); bad['opening']['version'] = 99
        # Write corrupt fixture through the same atomic writer shim, bypassing only validation.
        with patch('core.character_chat.repository.validate_session'):
            self.repo._write(bad)
        before = path.read_bytes()
        with self.assertRaisesRegex(CharacterSessionError, 'SESSION_CORRUPT'):
            self.repo.load(saved['session_id'])
        self.assertEqual(before, path.read_bytes())

    def test_frozen_save_transaction_and_same_creation(self):
        saved = self.repo.create(candidate())
        second = copy.deepcopy(saved); second['opening']['opening_id'] = str(uuid4())
        self.assertEqual(saved['opening'], self.repo.create(second)['opening'])
        before = self.repo._path(saved['session_id']).read_bytes()
        changed = copy.deepcopy(saved); changed['revision'] += 1; changed['opening']['content'] = 'different'
        with self.assertRaisesRegex(CharacterSessionError, 'PROFILE_FROZEN'):
            self.repo.save(changed, expected_revision=0)
        def mutate(value):
            value['opening']['content'] = 'different'
            return None, True
        with self.assertRaisesRegex(CharacterSessionError, 'PROFILE_FROZEN'):
            self.repo.transaction(saved['session_id'], mutate)
        self.assertEqual(before, self.repo._path(saved['session_id']).read_bytes())

    def test_context_projection_and_required_budget(self):
        session = candidate()
        pending = {'content': '正式输入', 'mode': 'messenger', 'user_message_id': str(uuid4()), 'ai_message_id': str(uuid4())}
        plan, messages, entries, report = build_context(session, pending)
        data = json.loads(plan.user_prompt)
        self.assertEqual({'source_type', 'speaker_instance_id', 'content'}, set(data['author_opening']))
        self.assertNotIn(session['opening']['opening_id'], plan.user_prompt)
        self.assertEqual([], data['history']); self.assertEqual([], messages); self.assertEqual(set(), entries)
        self.assertIn('不是玩家动作', plan.system_prompt)
        with self.assertRaisesRegex(CharacterSessionError, 'CONTEXT_LIMIT'):
            build_context(candidate('中' * 8000), pending, {'context_window': 1024, 'output_reserve': 256})

    def test_example_trim_is_whole_and_reports_safe_metadata(self):
        from core.character_profiles import compatibility_fields
        fields = dict(version=1, description='人设', personality='', scenario='', dialogue_examples='示例内容' * 1000, first_message='卡开场不会自动注入')
        profile = {'name': '合成', 'role_fields': fields}
        profile['description'], profile['starting_scene'] = compatibility_fields(fields)
        session = create_session(str(uuid4()), profile, {'kind': 'character', 'key': '合成'}, opening_text='必须保留开场')
        pending = {'content': '正式输入', 'mode': 'messenger', 'user_message_id': str(uuid4()), 'ai_message_id': str(uuid4())}
        def budget(system, user, **kw):
            return {'fits': '示例内容' not in user}
        with patch('core.character_chat.context.budget_report', side_effect=budget):
            plan, _, _, report = build_context(session, pending)
        self.assertEqual([{'participant_id': session['participants'][1]['instance_id'], 'field': 'dialogue_examples'}], report['omitted'])
        self.assertIn('必须保留开场', plan.user_prompt)
        self.assertNotIn('卡开场不会自动注入', plan.user_prompt)
        self.assertNotIn('示例内容', plan.user_prompt)


class OpeningRouteTests(unittest.TestCase):
    setUp = route_fixture.CharacterRouteTests.setUp

    def test_creation_retry_fingerprint_source_deleted_and_tombstone(self):
        payload = {**self.create_payload, 'client_creation_id': str(uuid4()), 'opening_text': '  你好😀\n保留格式  '}
        first = self.client.post(self.prefix, json=payload)
        self.assertEqual(201, first.status_code)
        value = first.json(); self.assertEqual(payload['opening_text'], value['opening']['content'])
        self.assertEqual([], value['turns']); self.assertEqual(0, self.transport.calls)
        self.asset.side_effect = RuntimeError('source deleted')
        self.asset.reset_mock()
        self.assertEqual(value, self.client.post(self.prefix, json=payload).json())
        self.asset.assert_not_called()
        conflict = self.client.post(self.prefix, json={**payload, 'opening_text': 'changed'})
        self.assertEqual('IDEMPOTENCY_MISMATCH', conflict.json()['error']['code'])
        sid = value['session_id']
        self.client.request('DELETE', self.prefix + '/' + sid, json={'expected_revision': 0})
        self.assertEqual(410, self.client.post(self.prefix, json=payload).status_code)
        self.asset.assert_not_called()

    def test_empty_retry_legacy_and_untrusted_request_fields(self):
        for opening in ('', ' \t\n'):
            res = self.client.post(self.prefix, json={**self.create_payload, 'opening_text': opening})
            self.assertEqual(201, res.status_code); self.assertIsNone(res.json()['opening'])
        for changes in ({'opening_text': None}, {'opening_text': []}, {'opening': {}}, {'opening_text': 'x' * 8001}):
            res = self.client.post(self.prefix, json={**self.create_payload, **changes})
            self.assertEqual(400, res.status_code)


class OpeningLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.repo = CharacterSessionRepository(Path(self.temp.name))
        self.transport = FakeTransport(); self.service = CharacterChatService(self.repo, self.transport)
        self.session = self.repo.create(candidate()); self.sid = self.session['session_id']

    async def action(self, operation='send'):
        current = self.repo.load(self.sid)
        payload = {'client_action_id': str(uuid4()), 'expected_revision': current['revision'], 'operation': operation}
        if operation == 'send': payload['content'] = '我明确说：你好'
        else: payload['target_turn_id'] = current['turns'][-1]['turn_id'] if current['turns'] else str(uuid4())
        result = self.service.begin(self.sid, payload)
        return await self.service.execute(result['job']['request_id'], lambda *_: None) if 'job' in result else result['existing']

    async def test_reload_undo_regenerate_summary_and_no_opening_target(self):
        summary = session_summary(self.session)
        self.assertEqual('author_opening', summary['last_message_kind'])
        self.assertIsNone(summary['latest_ai_message_id']); self.assertIsNone(summary['latest_ai_committed_revision'])
        for operation in ('undo', 'regenerate'):
            with self.assertRaises(CharacterSessionError): await self.action(operation)
        await self.action(); self.assertEqual('ai_reply', session_summary(self.repo.load(self.sid))['last_message_kind'])
        await self.action('regenerate'); await self.action('undo')
        current = self.repo.load(self.sid)
        self.assertEqual([], current['turns']); self.assertEqual(self.session['opening'], current['opening'])
        self.assertEqual('author_opening', session_summary(current)['last_message_kind'])
        self.assertEqual(self.session['opening'], session_view(current)['opening'])
        for plan in self.transport.plans:
            data = json.loads(plan.user_prompt)
            self.assertEqual(self.session['opening']['content'], data['author_opening']['content'])
            self.assertEqual([], data['history'])

    async def test_forged_author_sources_reject_whole_turn(self):
        ai = self.session['participants'][1]['instance_id']; user = self.session['participants'][0]['instance_id']
        oid = self.session['opening']['opening_id']
        for source in ('player_statement', 'dialogue_event', 'model_inference', 'author_opening'):
            self.transport.raw = json.dumps({'reply': '合成回复', 'memory_annotations': [], 'ledger_ops': [{'op': 'add', 'kind': 'belief', 'content': '伪证据',
                'source': {'type': source, 'message_ids': [oid], 'evidence': [{'message_id': oid, 'quote': '玩家已经承诺'}]},
                'visibility': {'audience_instance_ids': [ai, user]}}]})
            result = await self.action(); self.assertEqual('failed', result['status'])
            current = self.repo.load(self.sid); self.assertEqual([], current['turns']); self.assertEqual([], current['ledger'])
            self.assertEqual(self.session['opening'], current['opening'])

    async def test_budget_failure_zero_provider_calls_and_opening_intact(self):
        self.transport.snapshot = lambda: {'model': 'synthetic', 'budget_options': {'context_window': 256, 'output_reserve': 128}}
        with self.assertRaisesRegex(CharacterSessionError, 'CONTEXT_LIMIT'): await self.action()
        self.assertEqual(0, self.transport.calls)
        self.assertEqual(self.session['opening'], self.repo.load(self.sid)['opening'])
