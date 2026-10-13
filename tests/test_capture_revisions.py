import json
import tempfile
import unittest
from pathlib import Path

import yaml

from core.worldbook import save_worldbook_atomic
from core.worldbook_capture import WorldbookCaptureService
from core.worldbook_revisions import reconcile_capture_history
from tests.test_worldbook_capture import FakeAI
from tests.test_world_change_events import event
from utils.file_io import save_game_data


class CaptureRevisionTests(unittest.TestCase):
    def test_auto_update_and_retire_keep_id_and_restore_original(self):
        for operation, kind in [('update', 'update'), ('retire', 'expire')]:
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as root:
                path = Path(root) / 'worldbooks' / 'world.yml'
                save_worldbook_atomic(path, {'name': '世界', 'entries': [
                    {'id': 'rule1', 'name': '规则', 'content': '旧法令', 'keys': '法令'}]})
                original = yaml.safe_load(path.read_text(encoding='utf-8'))
                source = {'turn_id': 1, 'player': '继续', 'story': '法令今日生效。', 'source_message_ids': ['a']}
                save_game_data(root, {'history': {'story_turns': [source]}})
                candidate = {'operation': operation, 'target_entry_id': 'rule1', 'name': '新标题',
                    'content': '新法令', 'event_index': 0, 'risk': 'low', 'scope': 'social_system', 'confidence': 'high'}
                ai = FakeAI(json.dumps({'candidates': [candidate]}))
                result = WorldbookCaptureService(ai).capture(path, '继续', source['story'], review_all=False,
                    source_turn=source, save_dir=root, world_change_events=[event(change_kind=kind)])
                self.assertEqual(len(result['updated']), 1)
                saved = yaml.safe_load(path.read_text(encoding='utf-8'))
                self.assertEqual(saved['entries'][0]['id'], 'rule1')
                self.assertEqual(saved['entries'][0]['is_active'], operation != 'retire')
                self.assertEqual(reconcile_capture_history(saved, [])[0]['entries'], original['entries'])
                self.assertNotIn('capture_history', ai.last_user_prompt)

    def test_review_or_unmapped_evidence_keeps_old_rule(self):
        for review, index in [(True, 0), (False, 4), (False, None)]:
            with tempfile.TemporaryDirectory() as root:
                path = Path(root) / 'worldbooks' / 'world.yml'
                save_worldbook_atomic(path, {'name': '世界', 'entries': [{'id': 'rule1', 'content': '旧法令', 'name': '规则'}]})
                source = {'turn_id': 1, 'story': '法令今日生效。'}
                save_game_data(root, {'history': {'story_turns': [source]}})
                ai = FakeAI(json.dumps({'candidates': [{'operation': 'update', 'target_entry_id': 'rule1',
                    'name': '新规则', 'content': '新法令', 'event_index': index, 'risk': 'low', 'confidence': 'high'}]}))
                result = WorldbookCaptureService(ai).capture(path, '', source['story'], review_all=review,
                    source_turn=source, save_dir=root, world_change_events=[event(change_kind='update')])
                self.assertEqual(len(result['pending']), 1)
                self.assertEqual(yaml.safe_load(path.read_text(encoding='utf-8'))['entries'][0]['content'], '旧法令')
