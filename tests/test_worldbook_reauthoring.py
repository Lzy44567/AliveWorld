import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.worldbook_workshop import WorldbookWorkshop, WorkshopError
from core.worldbook_workshop_agent import WorldbookWorkshopAgent
from core.worldbook_reauthoring import reference_catalog, select_references
from core.worldbook_revisions import record_capture_changes
from api.v1.streaming import workshop_chat_transaction
from api.v1 import worldbook_workshop_routes as routes
from tests.test_worldbook_workshop_agent import FakeAI


class ReauthoringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / 'target.yml'
        self.book = {'name': '目标', 'overview': '魔力世界', 'entries': [{'id': 'one', 'name': '技法', 'content': '原规则'}]}
        self.target.write_text(yaml.safe_dump(self.book), encoding='utf-8')
        self.source = self.root / 'source.yml'
        self.source.write_text(yaml.safe_dump({'name': '参考', 'overview': '灵力世界', 'entries': [{'id': 'one', 'name': '参考技法', 'content': '参考内容'}], 'capture_history': [{'secret': '历史私密'}]}), encoding='utf-8')
        self.workshop = WorldbookWorkshop('rewrite', self.target, self.book)

    def test_references_scope_snapshot_budget_and_no_history(self):
        catalog = reference_catalog(self.target)
        self.assertEqual(list(catalog), ['source'])
        refs = select_references(catalog, ['source'])
        self.assertNotIn('历史私密', json.dumps(refs, ensure_ascii=False))
        for ids in [['../source'], ['source', 'source'], ['missing']]:
            with self.assertRaises(ValueError): select_references(catalog, ids)
        catalog['source']['overview'] = 'x' * 60001
        with self.assertRaises(ValueError): select_references(catalog, ['source'])

    def test_focused_request_proposes_only_and_publish_keeps_reference_unchanged(self):
        original = self.source.read_bytes()
        self.workshop.set_reauthoring(select_references(reference_catalog(self.target), ['source']), 'one')
        restored = WorldbookWorkshop.from_dict(self.workshop.to_dict())
        ai = FakeAI(json.dumps({'message': '适配建议', 'operations': [{'op': 'update_entry', 'entry_id': 'one', 'changes': {'content': '适配后规则'}}]}))
        result = WorldbookWorkshopAgent(ai).respond(restored, '按参考改写', 'adapt', commit_changes=True)
        self.assertEqual(len(ai.requests), 1)
        self.assertIn('参考内容', ai.requests[0][1])
        self.assertIn('定向重写', ai.requests[0][1])
        self.assertEqual(result['applied'], [])
        self.assertEqual(restored.draft['entries'][0]['content'], '原规则')
        restored.review_operations('proposed', [restored.proposed[0]['operation_id']], accept=True)
        self.assertEqual(restored.draft['entries'][0]['content'], '适配后规则')
        restored.undo()
        self.assertEqual(restored.draft['entries'][0]['content'], '原规则')
        restored.publish()
        self.assertEqual(self.source.read_bytes(), original)
        self.assertNotIn('references', yaml.safe_load(self.target.read_text(encoding='utf-8')))

    def test_off_target_and_save_failure_leave_session_unchanged(self):
        self.workshop.set_reauthoring(focus_entry_id='one')
        before = self.workshop.to_dict()
        ai = FakeAI('{"operations":[{"op":"update_overview","overview":"越界"}]}')
        with self.assertRaises(WorkshopError):
            workshop_chat_transaction(self.workshop, self.root / 'sessions', lambda w: WorldbookWorkshopAgent(ai).respond(w, '改写', 'evolve'))
        self.assertEqual(self.workshop.to_dict(), before)
        with patch.object(WorldbookWorkshop, 'save_session', side_effect=OSError()):
            with self.assertRaises(OSError):
                workshop_chat_transaction(self.workshop, self.root, lambda w: w.set_reauthoring([], ''))
        self.assertEqual(self.workshop.to_dict(), before)

    def test_http_selection_persists_clears_and_published_is_readonly(self):
        app = FastAPI(); app.include_router(routes.router)
        with patch.object(routes, '_get', return_value=self.workshop), patch.object(routes, 'WORKSHOP_DIR', self.root / 'sessions'):
            client = TestClient(app)
            base = '/workshops/rewrite'
            self.assertEqual(client.get(base + '/references').json()['items'][0]['source_id'], 'source')
            response = client.put(base + '/reauthoring', json={'reference_ids': ['source'], 'focus_entry_id': 'one'})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn('参考内容', response.text)
            saved = WorldbookWorkshop.from_dict(json.loads((self.root / 'sessions/rewrite.json').read_text(encoding='utf-8')))
            self.assertEqual(saved.focus_entry_id, 'one')
            self.assertEqual(len(saved.references), 1)
            self.assertEqual(client.put(base + '/reauthoring', json={'reference_ids': ['missing']}).status_code, 400)
            self.assertEqual(len(self.workshop.references), 1)
            self.assertEqual(client.put(base + '/reauthoring', json={'reference_ids': [], 'focus_entry_id': ''}).status_code, 200)
            self.assertEqual(self.workshop.references, [])
            self.workshop.publish()
            self.assertEqual(client.put(base + '/reauthoring', json={'reference_ids': ['source']}).status_code, 400)

    def test_old_workshop_is_not_granted_references(self):
        old = self.workshop.to_dict(); old.pop('references'); old.pop('focus_entry_id')
        restored = WorldbookWorkshop.from_dict(old)
        self.assertEqual(restored.references, [])
        self.assertEqual(restored.focus_entry_id, '')

    def test_local_references_follow_active_turns_without_changing_source(self):
        turn = {'turn_id': 1, 'player': '探索', 'story': '发现新规则'}
        book = record_capture_changes({'entries': []}, {'name': '参考', 'entries': [
            {'id': 'new', 'name': '新规则', 'content': '新规则内容', 'is_active': True}]}, turn)
        self.source.write_text(yaml.safe_dump(book), encoding='utf-8')
        original = self.source.read_bytes()
        self.workshop.local_save_path = str(self.root / 'story')
        app = FastAPI(); app.include_router(routes.router)
        game = SimpleNamespace(save_dir_path=self.workshop.local_save_path, history={'story_turns': [turn]})
        with patch.object(routes, '_get', return_value=self.workshop), patch.object(routes, 'WORKSHOP_DIR', self.root / 'sessions'), patch.dict(routes.active_sessions, {'test': game}, clear=True):
            client = TestClient(app)
            base = '/workshops/rewrite/reauthoring'
            self.assertEqual(client.put(base, json={'reference_ids': ['source']}).status_code, 200)
            self.assertEqual(len(self.workshop.references[0]['entries']), 1)
            game.history['story_turns'] = []
            self.assertEqual(len(self.workshop.references[0]['entries']), 1)  # Explicit snapshot, not a live link.
            self.assertEqual(client.put(base, json={'reference_ids': ['source']}).status_code, 200)
            self.assertEqual(self.workshop.references[0]['entries'], [])
            routes.active_sessions.clear()
            self.assertEqual(client.put(base, json={'reference_ids': ['source']}).status_code, 409)
            self.assertEqual(client.put(base, json={'reference_ids': []}).status_code, 200)
        self.assertEqual(self.source.read_bytes(), original)
