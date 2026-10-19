import copy
import tempfile
import threading
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.v1 import asset_workshop_routes as assets, generation_routes as controls, game_routes
from core.asset_workshop import AssetWorkshop
from core.generation_control import generation_scope, cancel_generation, GenerationCancelled


class GenerationRouteTests(unittest.TestCase):
    def test_workshop_json_and_stream_cancel_before_save(self):
        for suffix in ('', '/stream'):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as directory:
                workshop = AssetWorkshop('workshop', 'styles', Path(directory) / 'asset.yml', {'name': 'style', 'content': 'original'})
                before = copy.deepcopy(workshop.to_dict())
                entered, release = threading.Event(), threading.Event()
                def respond(_agent, candidate, *args, **kwargs):
                    candidate.draft['content'] = 'uncommitted'
                    entered.set()
                    if not release.wait(5):
                        raise RuntimeError('test timed out')
                    return {'message': 'generated'}
                app = FastAPI()
                app.include_router(assets.router, prefix='/workshops')
                app.include_router(controls.router, prefix='/controls')
                rid = str(uuid4())
                result = []
                with patch.object(assets, 'load_asset_workshop', return_value=workshop), patch.object(assets, '_engine', return_value=object()), patch.object(assets, 'WORKSHOP_DIR', Path(directory)), patch.object(assets.AssetWorkshopAgent, 'respond', respond), TestClient(app) as client:
                    worker = threading.Thread(target=lambda: result.append(client.post('/workshops/workshop/chat' + suffix, json={'generation_id': rid, 'message': 'test'})))
                    worker.start()
                    try:
                        self.assertTrue(entered.wait(5))
                        wrong = client.post(f'/controls/workshop/workshop/{uuid4()}/stop')
                        self.assertEqual(wrong.json()['status'], 'not_running')
                        stopped = client.post(f'/controls/workshop/workshop/{rid}/stop')
                        self.assertEqual(stopped.json()['status'], 'cancelling')
                    finally:
                        release.set()
                        worker.join(5)
                    self.assertFalse(worker.is_alive())
                    self.assertIn('generation_cancelled', result[0].text)
                    self.assertEqual(workshop.to_dict(), before)
                    self.assertFalse((Path(directory) / 'workshop.json').exists())
                    self.assertEqual(client.post(f'/controls/workshop/workshop/{rid}/stop').json()['status'], 'not_running')

    def test_story_cancel_restores_checkpoint_and_never_dispatches_capture(self):
        class Game:
            save_dir_path = 'unused'
            value = 'original'
            dispatched = False
            def capture_transaction_state(self): return self.value
            def restore_transaction_state(self, value): self.value = value
            def export_save_data(self): return {'value': self.value}
            def dispatch_committed_worldbook_captures(self): self.dispatched = True
        game = Game()
        def operation():
            game.value = 'uncommitted'
            cancel_generation(('story', 'test'), 'request')
        with patch.object(game_routes, 'save_game_data') as save:
            with generation_scope(('story', 'test'), 'request'), self.assertRaises(GenerationCancelled):
                game_routes._persisted_story_mutation(game, operation)
            save.assert_not_called()
        self.assertEqual(game.value, 'original')
        self.assertFalse(game.dispatched)
