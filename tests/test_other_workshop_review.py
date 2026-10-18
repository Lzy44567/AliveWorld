import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.v1 import asset_workshop_routes, preference_workshop_routes
from core.asset_workshop import AssetWorkshop
from core.preference_workshop import PreferenceWorkshop, PreferenceWorkshopError


class OtherWorkshopReviewTests(unittest.TestCase):
    def test_all_asset_types_http_review_persistence_and_failure(self):
        for kind, field in [('characters', 'description'), ('styles', 'content'), ('entities', 'description')]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                workshop = AssetWorkshop(kind, kind, root / 'asset.yml', {'name': 'test', field: 'old'})
                workshop.propose_operations([
                    {'op': 'update_fields', 'operation_id': 'a', 'changes': {field: 'new'}},
                    {'op': 'update_fields', 'operation_id': 'b', 'changes': {'tags': ['tag']}},
                ])
                app = FastAPI()
                app.include_router(asset_workshop_routes.router)
                with patch.object(asset_workshop_routes, 'load_asset_workshop', return_value=workshop), patch.object(asset_workshop_routes, 'WORKSHOP_DIR', root), TestClient(app, raise_server_exceptions=False) as client:
                    body = {'source': 'proposed', 'operation_ids': ['a'], 'accept': True}
                    response = client.post(f'/{kind}/review', json=body)
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(workshop.draft[field], 'new')
                    self.assertEqual([item['operation_id'] for item in workshop.proposed], ['b'])
                    restored = AssetWorkshop.from_dict(json.loads((root / f'{kind}.json').read_text(encoding='utf-8')))
                    self.assertEqual(restored.proposed, workshop.proposed)
                    self.assertEqual(restored.draft, workshop.draft)
                    self.assertFalse(workshop.target_path.exists())
                    before = copy.deepcopy(workshop.to_dict())
                    with patch.object(AssetWorkshop, 'save_session', side_effect=OSError('disk full')):
                        response = client.post(f'/{kind}/review', json={**body, 'operation_ids': ['b'], 'accept': False})
                    self.assertEqual(response.status_code, 500)
                    self.assertEqual(workshop.to_dict(), before)
                    self.assertEqual(client.post(f'/{kind}/review', json=body).status_code, 400)
                    client.post(f'/{kind}/undo')
                    self.assertEqual(workshop.draft[field], 'old')
                    self.assertEqual(client.post(f'/{kind}/review', json={**body, 'operation_ids': ['b'], 'accept': False}).status_code, 200)
                    self.assertEqual(workshop.proposed, [])

    def test_preferences_batch_undo_and_atomic_conflict(self):
        workshop = PreferenceWorkshop('prefs', {'preferences': [{'id': 'p', 'statement': 'old', 'status': 'candidate'}]})
        workshop.propose_operations([
            {'op': 'update_preference', 'operation_id': 'a', 'preference_id': 'p', 'changes': {'statement': 'new'}},
            {'op': 'set_status', 'operation_id': 'b', 'preference_id': 'p', 'status': 'active'},
            {'op': 'delete_preference', 'operation_id': 'c', 'preference_id': 'p'},
        ])
        workshop.review_operations('proposed', ['a', 'b'], True)
        self.assertEqual(workshop.draft[0]['status'], 'active')
        self.assertEqual(len(workshop.proposed), 1)
        workshop.undo()
        self.assertEqual(workshop.draft[0]['statement'], 'old')
        self.assertEqual(workshop.draft[0]['status'], 'candidate')
        workshop.propose_operations([
            {'op': 'delete_preference', 'operation_id': 'delete', 'preference_id': 'p'},
            {'op': 'set_status', 'operation_id': 'update', 'preference_id': 'p', 'status': 'active'},
        ])
        before = copy.deepcopy(workshop.to_dict())
        with self.assertRaises(PreferenceWorkshopError):
            workshop.review_operations('proposed', ['delete', 'update'], True)
        self.assertEqual(workshop.to_dict(), before)

    def test_preference_pending_http_and_published_readonly(self):
        workshop = PreferenceWorkshop('prefs', {'preferences': []})
        workshop.apply_operations([{'op': 'add_preference', 'operation_id': 'a', 'preference': {'statement': 'test', 'status': 'active'}}])
        app = FastAPI()
        app.include_router(preference_workshop_routes.router)
        with tempfile.TemporaryDirectory() as directory, patch.object(preference_workshop_routes, 'load_preference_workshop', return_value=workshop), patch.object(preference_workshop_routes, 'WORKSHOP_DIR', Path(directory)), TestClient(app) as client:
            body = {'source': 'pending', 'operation_ids': ['a'], 'accept': True}
            response = client.post('/prefs/review', json=body)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(workshop.pending, [])
            self.assertEqual(workshop.draft[0]['status'], 'active')
            workshop.published = True
            self.assertEqual(client.post('/prefs/review', json=body).status_code, 400)
