from pathlib import Path
import tempfile
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.v1.worldbook_activity_routes import router
from core.game_session import GameSession
from core.session_manager import active_sessions
from core.worldbook import save_worldbook_atomic
from core.worldbook_revisions import record_capture_changes
from api.v1.local_asset_routes import router as asset_router
from core.worldbook import worldbook_revision
import yaml


class ActivityRoutesTests(unittest.TestCase):
    def test_readonly_details_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            game = GameSession(None, save_name='test', save_dir_path=directory)
            active_sessions['activity-test'] = game
            self.addCleanup(active_sessions.pop, 'activity-test', None)
            turn = {'turn_id': 1, 'player': '行动', 'story': '事实'}
            game.history['story_turns'] = [turn]
            path = Path(directory) / 'worldbooks' / 'file.yml'
            path.parent.mkdir()
            book = record_capture_changes({'entries': []}, {'name': '不同显示名', 'entries': [
                {'id': 'x', 'name': '隐藏标题', 'content': '隐藏内容', 'tags': []}]}, turn)
            save_worldbook_atomic(path, book)
            before = path.read_bytes()
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            url = '/activity-test/worldbook-activity'
            plain = client.get(url)
            self.assertEqual(plain.status_code, 200)
            self.assertNotIn('隐藏', plain.text)
            self.assertEqual(plain.json()['items'][0]['book_id'], 'file')
            self.assertIn('隐藏内容', client.get(url + '?details=true').text)
            self.assertEqual(client.get(url + '?limit=500').status_code, 422)
            self.assertEqual(client.get('/missing/worldbook-activity').status_code, 404)
            self.assertEqual(path.read_bytes(), before)

    def test_review_uses_exact_file_not_duplicate_display_name(self):
        with tempfile.TemporaryDirectory() as directory:
            game = GameSession(None, save_name='test', save_dir_path=directory)
            active_sessions['activity-file-test'] = game
            self.addCleanup(active_sessions.pop, 'activity-file-test', None)
            root = Path(directory) / 'worldbooks'
            root.mkdir()
            for key in ('a', 'b'):
                save_worldbook_atomic(root / f'{key}.yml', {'name': '同名书', 'entries': [
                    {'id': 'pending', 'name': key, 'content': key, 'tags': ['待确认']}]})
            before_a = (root / 'a.yml').read_bytes()
            app = FastAPI()
            app.include_router(asset_router)
            client = TestClient(app)
            result = client.post('/activity-file-test/worldbooks/b/review?by_id=true', json={
                'expected_revision': worldbook_revision((root / 'b.yml').read_bytes()),
                'decisions': [{'id': 'pending', 'accept': False}]})
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual((root / 'a.yml').read_bytes(), before_a)
            self.assertEqual(yaml.safe_load((root / 'b.yml').read_bytes())['entries'], [])
