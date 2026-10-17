import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.v1 import worldbook_workshop_routes as routes
from core.worldbook_workshop import WorldbookWorkshop


class WorkshopReviewApiTests(unittest.TestCase):
    def test_selected_review_isolated_and_atomic_on_disk_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            global_book = WorldbookWorkshop('global', root / 'global/book.yml', {'name': 'same'})
            local_book = WorldbookWorkshop('local', root / 'story/worldbooks/book.yml', {'name': 'same'})
            for item in [global_book, local_book]:
                item.propose_operations([{'op': 'update_overview', 'operation_id': 'overview', 'overview': 'new'},
                                         {'op': 'set_axioms', 'operation_id': 'rules', 'axioms': ['rule']}])
            original_global = copy.deepcopy(global_book.to_dict())
            app = FastAPI()
            app.include_router(routes.router)
            with patch.object(routes, 'load_worldbook_workshop', side_effect={'global': global_book, 'local': local_book}.get), \
                 patch.object(routes, 'WORKSHOP_DIR', root / 'sessions'), \
                 TestClient(app, raise_server_exceptions=False) as client:
                response = client.post('/workshops/local/review', json={'source': 'proposed', 'operation_ids': ['rules'], 'accept': True})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(local_book.draft['axioms'], ['rule'])
                self.assertEqual(len(local_book.proposed), 1)
                self.assertEqual(global_book.to_dict(), original_global)
                self.assertFalse(global_book.target_path.exists())
                self.assertFalse(local_book.target_path.exists())
                before = copy.deepcopy(local_book.to_dict())
                with patch.object(WorldbookWorkshop, 'save_session', side_effect=OSError('disk full')):
                    failed = client.post('/workshops/local/review', json={'source': 'proposed', 'operation_ids': ['overview'], 'accept': True})
                self.assertEqual(failed.status_code, 500)
                self.assertEqual(local_book.to_dict(), before)
                stale = client.post('/workshops/local/review', json={'source': 'proposed', 'operation_ids': ['rules'], 'accept': True})
                self.assertEqual(stale.status_code, 400)
                client.post('/workshops/local/undo')
                self.assertEqual(local_book.draft['axioms'], [])
                for item in [global_book, local_book]:
                    item.apply_operations([{'op': 'set_axioms', 'operation_id': 'pending', 'axioms': ['pending']}])
                accepted = client.post('/workshops/local/review', json={'source': 'pending', 'operation_ids': ['pending'], 'accept': True})
                self.assertEqual(accepted.status_code, 200)
                self.assertEqual(global_book.draft['axioms'], [])
                self.assertEqual(len(global_book.pending), 1)
                rejected = client.post('/workshops/local/review', json={'source': 'proposed', 'operation_ids': ['overview'], 'accept': False})
                self.assertEqual(rejected.status_code, 200)
                self.assertEqual(local_book.draft['overview'], '')
                saved = client.put('/workshops/local/creative-brief', json={'creative_brief': 'local goal'})
                self.assertEqual(saved.status_code, 200)
                self.assertEqual(global_book.creative_brief, '')
                invalid = client.put('/workshops/local/creative-brief', json={'creative_brief': 'x' * 2001})
                self.assertEqual(invalid.status_code, 422)
