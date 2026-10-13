import copy
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.session_manager import register_session, unregister_session
from core.worldbook import save_worldbook_atomic, worldbook_revision
from api.v1.local_asset_routes import router

from core.worldbook import normalize_entry
from core.worldbook_review import review_proposals, entry_revision, WorldbookReviewError
from core.worldbook_revisions import record_capture_changes, reconcile_capture_history


class WorldbookReviewTests(unittest.TestCase):
    def setup_book(self, operation='update'):
        source = {'turn_id': 1, 'story': '规则生效', 'source_message_ids': ['one']}
        target = normalize_entry({'id': 'rule', 'name': '旧规则', 'content': '旧内容'})
        proposal = normalize_entry({'id': 'proposal', 'name': '新规则', 'content': '新内容',
            'tags': ['待确认'], 'is_active': False, 'pending_operation': operation,
            'replaces_entry_id': 'rule', 'proposal_target_revision': entry_revision(target)})
        book = record_capture_changes({'entries': [target]}, {'entries': [target, proposal]}, source)
        return book, source, target

    def test_accept_update_and_retire_remain_reversible(self):
        for operation in ('update', 'retire'):
            book, source, target = self.setup_book(operation)
            reviewed = review_proposals(book, [{'id': 'proposal', 'accept': True}], [source])
            self.assertEqual(len(reviewed['entries']), 1)
            self.assertEqual(reviewed['entries'][0]['id'], 'rule')
            self.assertEqual(reviewed['entries'][0]['is_active'], operation != 'retire')
            self.assertEqual(reconcile_capture_history(reviewed, [])[0]['entries'], [target])

    def test_rejected_proposal_cannot_reappear_after_undo(self):
        book, source, target = self.setup_book()
        rejected = review_proposals(book, [{'id': 'proposal', 'accept': False}], [source])
        self.assertEqual(reconcile_capture_history(rejected, [])[0]['entries'], [target])
        self.assertEqual(rejected['capture_reviews'][0]['decision'], 'rejected')

    def test_target_manual_edit_or_stale_source_rejects_without_mutation(self):
        for manual in (True, False):
            book, source, _ = self.setup_book()
            if manual:
                book['entries'][0]['content'] = '玩家独立修改'
            before = copy.deepcopy(book)
            with self.assertRaises(WorldbookReviewError):
                review_proposals(book, [{'id': 'proposal', 'accept': True}], [source] if manual else [])
            self.assertEqual(book, before)

    def test_batch_failure_does_not_apply_first_decision(self):
        book, source, _ = self.setup_book()
        before = copy.deepcopy(book)
        with self.assertRaises(WorldbookReviewError):
            review_proposals(book, [{'id': 'proposal', 'accept': True}, {'id': 'missing', 'accept': True}], [source])
        self.assertEqual(book, before)

    def test_later_manual_changes_survive_source_undo(self):
        book, source, _ = self.setup_book()
        reviewed = review_proposals(book, [{'id': 'proposal', 'accept': True}], [source])
        reviewed['entries'][0]['content'] = '接受后玩家另行修改'
        self.assertEqual(reconcile_capture_history(reviewed, [])[0]['entries'][0]['content'], '接受后玩家另行修改')

    def test_http_review_uses_revision_and_persists_source(self):
        with tempfile.TemporaryDirectory() as root:
            book, source, target = self.setup_book()
            book['name'] = '验收世界'
            path = Path(root) / 'worldbooks' / 'book.yml'
            save_worldbook_atomic(path, book)
            game = SimpleNamespace(save_dir_path=root, history={'story_turns': [source]})
            register_session('review-test', game)
            app = FastAPI()
            app.include_router(router)
            try:
                with TestClient(app) as client:
                    listed = client.get('/review-test/local_assets').json()['worldbooks'][0]
                    data = {'expected_revision': listed['edit_revision'], 'decisions': [{'id': 'proposal', 'accept': True}]}
                    result = client.post('/review-test/worldbooks/验收世界/review', json=data)
                    self.assertEqual(result.status_code, 200, result.text)
                    self.assertEqual(result.json()['book']['entries'][0]['content'], '新内容')
                    self.assertEqual(client.post('/review-test/worldbooks/验收世界/review', json=data).status_code, 409)
                    game.history['story_turns'] = []
                    restored = client.get('/review-test/local_assets').json()['worldbooks'][0]
                    self.assertEqual(restored['entries'], [target])
                    self.assertEqual(restored['edit_revision'], worldbook_revision(path.read_bytes()))
            finally:
                unregister_session('review-test')
