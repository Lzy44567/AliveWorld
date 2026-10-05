"""C2 opt-in projection, request freezing and revocation without learning."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4
from types import SimpleNamespace

from core.character_chat.preferences import project_preferences, validate_settings, session_settings, load_preferences
from core.character_chat.models import create_session, validate_session, CharacterSessionError
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat.service import CharacterChatService, session_view
from core.character_chat.context import build_context
from tests.test_character_chat_lifecycle import FakeTransport


OFF = {'enabled': False, 'include_sensitive': False}
ON = {'enabled': True, 'include_sensitive': False}


def item(statement='合成偏好', **updates):
    return {'statement': statement, 'category': 'story', 'polarity': 'prefer', 'status': 'active',
            'manual_override': True, 'sensitive': False, 'evidence': ['PRIVATE_EVIDENCE'], **updates}


def session():
    return create_session(str(uuid4()), {'name': '合成', 'description': '固定人设'}, {'kind': 'character', 'key': '合成'})


class PreferenceProjectionTests(unittest.TestCase):
    def test_legacy_default_and_strict_authorization(self):
        value = session(); before = copy.deepcopy(value)
        self.assertEqual(OFF, session_settings(value)); self.assertEqual(OFF, session_view(value)['preference_settings'])
        self.assertEqual(before, value)
        for bad in (None, [], {}, {'enabled': 1, 'include_sensitive': False}, {**ON, 'unknown': True}, {'enabled': False, 'include_sensitive': True}):
            with self.assertRaises(ValueError): validate_settings(bad)
            value['extensions']['character_preferences'] = bad
            with self.assertRaises(CharacterSessionError): validate_session(value)

    def test_confirmed_only_and_whitelist(self):
        profile = {'preferences': [item(), item('候选', status='candidate'), item('已停用', status='disabled'),
            item('自动升为active', manual_override=False, source_type='inferred'),
            item('明确声明', manual_override=False, source_type='declared')]}
        before = copy.deepcopy(profile)
        result = project_preferences(profile, ON, {})
        self.assertEqual(['合成偏好', '明确声明'], [x['statement'] for x in result])
        self.assertNotIn('PRIVATE_EVIDENCE', json.dumps(result)); self.assertEqual(before, profile)
        self.assertTrue(all(set(x) == {'category', 'polarity', 'statement'} for x in result))

    def test_categories_and_sensitive_require_explicit_authorization(self):
        profile = {'preferences': [item('普通'), item('敏感', sensitive=True), item('成人', category='adult'),
            item('非法', sensitive='false'), item('未知', category='unknown'), item('动作', category='action')]}
        self.assertEqual(['普通'], [x['statement'] for x in project_preferences(profile, ON, {'preferenceActionEnabled': False})])
        result = project_preferences(profile, {**ON, 'include_sensitive': True}, {'preferenceAdultEnabled': False, 'preferenceActionEnabled': False})
        self.assertEqual(['普通', '敏感'], [x['statement'] for x in result])

    def test_whole_unicode_limits_dedup_and_invalid_values(self):
        profile = {'preferences': [item('😀' * 400) for _ in range(2)] + [item(str(i) + '字' * 398) for i in range(6)] +
                   [item('超' * 401), item('尾项'), item([], category='story'), item('未知方向', polarity=['prefer'])]}
        result = project_preferences(profile, ON, {})
        self.assertLessEqual(sum(len(x['statement']) for x in result), 2400)
        self.assertEqual('😀' * 400, result[0]['statement']); self.assertEqual(1, sum(x['statement'] == '😀' * 400 for x in result))
        self.assertTrue(all(len(x['statement']) <= 400 for x in result)); self.assertIn('尾项', [x['statement'] for x in result])
        self.assertEqual(20, len(project_preferences({'preferences': [item(str(i)) for i in range(30)]}, ON, {})))

    def test_disabled_does_not_read_disk_or_repository(self):
        with patch('core.user_preferences.UserPreferenceRepository') as repository:
            self.assertEqual([], load_preferences(OFF)); repository.assert_not_called()
        self.assertEqual([], project_preferences({'preferences': [item()]}, OFF, {}))

    def test_budget_discards_whole_preferences_before_required_context(self):
        value = session(); before = copy.deepcopy(value)
        pending = {'content': '继续', 'mode': 'messenger', 'user_message_id': str(uuid4()), 'ai_message_id': str(uuid4())}
        prefs = [item()['statement']]
        projected = [{'statement': prefs[0], 'category': 'story', 'polarity': 'prefer'}]
        def budget(system, user, **kwargs):
            return {'fits': 'user_preferences' not in user}
        with patch('core.character_chat.context.budget_report', side_effect=budget):
            plan, messages, ids, report = build_context(value, pending, preferences=projected)
        self.assertNotIn('user_preferences', plan.user_prompt)
        self.assertEqual([{'field': 'user_preferences'}], report['omitted'])
        self.assertEqual([], messages); self.assertEqual(set(), ids); self.assertEqual(before, value)
        self.assertEqual(prefs[0], projected[0]['statement'])

    def test_loader_reads_only_enabled_categories_and_does_not_write_profile(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'config.yml'; path.write_text('settings:\n  preferenceStoryEnabled: false\n', encoding='utf-8')
            profile = {'preferences': [item('排除剧情'), item('动作保留', category='action')]}
            repository = Mock(); repository.load.return_value = profile
            with patch('utils.runtime_paths.PATHS', SimpleNamespace(config_file=path)), patch('core.user_preferences.UserPreferenceRepository', return_value=repository):
                result = load_preferences(ON)
            self.assertEqual(['动作保留'], [x['statement'] for x in result]); repository.save.assert_not_called()
            self.assertEqual('settings:\n  preferenceStoryEnabled: false\n', path.read_text(encoding='utf-8'))


class PreferenceServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.repo = CharacterSessionRepository(Path(self.temp.name)); self.transport = FakeTransport()
        self.source = [{'statement': 'FROZEN_PREFERENCE', 'category': 'story', 'polarity': 'prefer'}]
        self.loader = Mock(side_effect=lambda _: copy.deepcopy(self.source))
        self.service = CharacterChatService(self.repo, self.transport, preference_loader=self.loader)
        self.value = self.repo.create(session()); self.sid = self.value['session_id']

    def begin(self, operation='send', target=None):
        payload = {'client_action_id': str(uuid4()), 'expected_revision': self.repo.load(self.sid)['revision'], 'operation': operation, 'delivery': 'stream'}
        if operation == 'send': payload['content'] = '继续'
        else: payload['target_turn_id'] = target
        return self.service.begin(self.sid, payload)

    def settings(self, value):
        return self.service.metadata(self.sid, self.repo.load(self.sid)['revision'], preference_settings=value)

    async def test_default_zero_read_cas_persistence_and_frozen_request(self):
        first = self.begin(); await self.service.execute(first['job']['request_id'], lambda *_: None)
        self.loader.assert_not_called()
        updated = self.settings(ON); self.assertEqual(ON, updated['preference_settings'])
        with self.assertRaises(CharacterSessionError) as stale:
            self.service.metadata(self.sid, 0, preference_settings=OFF)
        self.assertEqual('REVISION_CONFLICT', stale.exception.code)
        started = self.begin()
        with self.assertRaises(CharacterSessionError) as busy: self.settings(OFF)
        self.assertEqual('SESSION_BUSY', busy.exception.code)
        self.source[0]['statement'] = 'NEW_GLOBAL_PREFERENCE'
        await self.service.execute(started['job']['request_id'], lambda *_: None)
        self.assertIn('FROZEN_PREFERENCE', self.transport.plans[-1].user_prompt)
        self.assertNotIn('NEW_GLOBAL_PREFERENCE', self.transport.plans[-1].user_prompt)
        self.assertNotIn('FROZEN_PREFERENCE', json.dumps(self.repo.load(self.sid)))
        fresh = CharacterChatService(self.repo, self.transport, preference_loader=self.loader)
        self.assertEqual(ON, session_view(fresh.repository.load(self.sid))['preference_settings'])

    async def test_retry_rechecks_revoked_authorization_without_old_snapshot(self):
        self.settings(ON); started = self.begin(); job = started['job']
        self.transport.raw = 'invalid'
        result = await self.service.execute(job['request_id'], lambda *_: None)
        self.assertEqual('failed', result['status']); self.assertEqual(1, self.loader.call_count)
        self.settings(OFF); self.transport.raw = None
        resumed = self.service.begin(self.sid, {'expected_revision': self.repo.load(self.sid)['revision'], 'delivery': 'non_stream',
            'retry_of': job['request_id'], 'retry_token': str(uuid4())}, retry_action_id=job['action_id'])
        await self.service.execute(resumed['job']['request_id'], lambda *_: None)
        self.assertEqual(1, self.loader.call_count); self.assertNotIn('user_preferences', self.transport.plans[-1].user_prompt)
        self.assertNotIn('FROZEN_PREFERENCE', json.dumps(self.repo.load(self.sid)))

    async def test_idempotent_replay_and_regenerate_use_current_authorization(self):
        self.settings(ON); started = self.begin(); job = started['job']
        result = await self.service.execute(job['request_id'], lambda *_: None)
        replay = self.service.begin(self.sid, {'client_action_id': job['action_id'], 'expected_revision': 0, 'operation': 'send', 'content': '继续'})
        self.assertIn('existing', replay); self.assertEqual(1, self.loader.call_count)
        self.source[0]['statement'] = 'CHANGED_PREFERENCE'
        regenerated = self.begin('regenerate', result['turn_id'])
        await self.service.execute(regenerated['job']['request_id'], lambda *_: None)
        self.assertIn('CHANGED_PREFERENCE', self.transport.plans[-1].user_prompt)
        self.assertEqual(2, self.loader.call_count)
