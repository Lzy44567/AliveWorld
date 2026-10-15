import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.v1 import worldbook_workshop_routes as routes
from core.session_manager import register_session, unregister_session
from core.worldbook import normalize_worldbook, save_worldbook_atomic
from core.worldbook_revisions import record_capture_changes
from core.worldbook_workshop import WorldbookWorkshop


class WorkshopCaptureTests(unittest.TestCase):
    def test_open_projects_undo_and_stale_publish_keeps_draft(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            path = root / 'worldbooks' / 'book.yml'
            source = {'turn_id': 1, 'story': '规则出现', 'source_message_ids': ['first']}
            before = normalize_worldbook({'name': 'book'})
            after = normalize_worldbook({'name': 'book', 'entries': [{'id': 'new', 'name': '新规则', 'content': '旧未来'}]})
            save_worldbook_atomic(path, record_capture_changes(before, after, source))
            game = SimpleNamespace(save_dir_path=str(root), history={'story_turns': [source]})
            register_session('workshop-capture', game)
            app = FastAPI()
            app.include_router(routes.router)
            sessions = root / 'workshops'
            try:
                with patch.object(routes, 'WORKSHOP_DIR', sessions), TestClient(app) as client:
                    started = client.post('/workshops/start', json={'session_id': 'workshop-capture', 'worldbook_name': 'book'}).json()
                    ident = started['workshop_id']
                    self.assertEqual(started['draft']['entries'][0]['id'], 'new')
                    workshop = routes.active_workshops[ident]
                    restored = WorldbookWorkshop.from_dict(workshop.to_dict())
                    self.assertEqual(restored.local_save_path, str(root))
                    workshop.apply_operations([{'op': 'update_overview', 'overview': '人工草稿'}])
                    original = path.read_bytes()
                    game.history['story_turns'] = []
                    response = client.post(f'/workshops/{ident}/publish', json={})
                    self.assertEqual(response.status_code, 409, response.text)
                    self.assertEqual(path.read_bytes(), original)
                    self.assertFalse(workshop.published)
                    workshop.local_save_path = None
                    with patch.object(routes, 'SAVE_DIR', root.parent):
                        legacy = client.post(f'/workshops/{ident}/publish', json={})
                    self.assertEqual(legacy.status_code, 409, legacy.text)
                    opened = client.post('/workshops/start', json={'session_id': 'workshop-capture', 'worldbook_name': 'book'}).json()
                    self.assertEqual(opened['draft']['entries'], [])
                    published = client.post(f"/workshops/{opened['workshop_id']}/publish", json={})
                    self.assertEqual(published.status_code, 200, published.text)
            finally:
                unregister_session('workshop-capture')
                for ident, item in list(routes.active_workshops.items()):
                    if item.local_save_path == str(root):
                        routes.active_workshops.pop(ident)
