import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import yaml

from api.v1.worldbook_collaboration_routes import router
from core.game_session import GameSession
from core.session_manager import active_sessions, mutation_guard, save_identity
from core.worldbook_collaboration import rule_catalog, collect_conflicts


class CollaborationRoutesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = GameSession(None, save_name='test', save_dir_path=self.temp.name)
        active_sessions['collaboration-test'] = self.game
        self.addCleanup(active_sessions.pop, 'collaboration-test', None)
        path = Path(self.temp.name) / 'worldbooks'
        path.mkdir()
        for name, content in [('main', '禁止飞行'), ('extra', '允许飞行')]:
            (path / f'{name}.yml').write_text(yaml.safe_dump({
                'name': name, 'entries': [{'id': 'same', 'name': '规则', 'content': content, 'tags': ['常驻']}],
            }), encoding='utf-8')
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.url = '/collaboration-test/worldbook-collaboration'

    def update(self, **fields):
        revision = self.client.get(self.url).json()['revision']
        return self.client.patch(self.url, json={'expected_revision': revision, **fields})

    def test_configuration_persists_and_busy_stale_are_rejected(self):
        original = self.client.get(self.url).json()
        self.assertEqual(original['primary_book'], '')
        self.assertFalse((Path(self.temp.name) / 'session_state.json').exists())
        self.assertEqual(self.update(primary_book='main').status_code, 200)
        saved = json.loads((Path(self.temp.name) / 'session_state.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['worldbook_collaboration']['primary_book'], 'main')
        self.assertEqual(self.client.patch(self.url, json={'expected_revision': original['revision'], 'review': True}).status_code, 409)
        with mutation_guard('story', save_identity(self.temp.name)):
            self.assertEqual(self.update(review=True).status_code, 409)
        self.assertEqual(self.update(primary_book='missing').status_code, 400)
        with patch('api.v1.worldbook_collaboration_routes.save_game_data', side_effect=OSError()):
            self.assertEqual(self.update(review=True).status_code, 500)
        self.assertFalse(self.game.worldbook_collaboration['review'])

    def test_context_filters_overlay_restore_and_runtime_rollback(self):
        self.update(primary_book='main')
        self.game._refresh_local_context()
        rules = rule_catalog(self.game.ctx_mgr.world_books)
        keep = next(ref for ref, rule in rules.items() if rule['book_id'] == 'main')
        disable = next(ref for ref, rule in rules.items() if rule['book_id'] == 'extra')
        turn = {'turn_id': 1, 'player': '飞行', 'story': '不能飞'}
        self.game.history['story_turns'] = [turn]
        before = self.game.capture_transaction_state()
        self.game.worldbook_collaboration, _ = collect_conflicts([{
            'keep': keep, 'disable': disable, 'keep_quote': '禁止飞行', 'disable_quote': '允许飞行',
            'scope': '同一地区', 'reason': '互斥',
        }], state=self.game.worldbook_collaboration, books=self.game.ctx_mgr.world_books,
            supplied_rules=rules, source_turn=turn)
        self.game._refresh_local_context()
        self.assertNotIn('允许飞行', self.game.build_visible_world_info('飞行')[0])
        item = self.client.get(self.url).json()['conflicts'][0]
        self.assertEqual(self.update(conflict_id=item['id'], decision='restore').status_code, 200)
        self.game._refresh_local_context()
        self.assertIn('允许飞行', self.game.build_visible_world_info('飞行')[0])
        self.game.restore_transaction_state(before)
        self.assertEqual(self.game.worldbook_collaboration['conflicts'], [])


if __name__ == '__main__':
    unittest.main()
