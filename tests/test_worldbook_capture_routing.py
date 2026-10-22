import unittest
import tempfile
import json
from pathlib import Path
import yaml

from core.worldbook_capture_routing import route_candidates
from core.worldbook_capture_batch import capture_books
from core.worldbook_capture import WorldbookCaptureService
from core.worldbook import save_worldbook_atomic


class CaptureRoutingTests(unittest.TestCase):
    def setUp(self):
        self.books = {'main': {'entries': [{'id': 'same', 'name': '规则'}]},
                      'knowledge': {'entries': [{'id': 'same', 'name': '规则'}]}}

    def test_exact_book_survives_duplicate_entry_names_and_ids(self):
        groups, skipped = route_candidates({'candidates': [
            {'operation': 'retire', 'target_book_id': 'knowledge', 'target_entry_id': 'same'}]}, self.books)
        self.assertEqual(list(groups), ['knowledge'])
        self.assertEqual(skipped, [])

    def test_unknown_revision_never_becomes_addition(self):
        groups, skipped = route_candidates({'candidates': [
            {'operation': 'update', 'target_book_id': 'missing', 'target_entry_id': 'same'}]}, self.books)
        self.assertEqual(groups, {})
        self.assertEqual(len(skipped), 1)

    def test_unknown_addition_is_reviewed_fallback(self):
        groups, _ = route_candidates({'candidates': [
            {'operation': 'add', 'target_book_id': '../global', 'risk': 'low'}]}, self.books)
        self.assertEqual(groups[''][0]['risk'], 'high')

    def test_explicit_uncertainty_and_known_destination(self):
        groups, _ = route_candidates({'candidates': [
            {'operation': 'add', 'target_book_id': ''},
            {'operation': 'add', 'target_book_id': 'main'}]}, self.books)
        self.assertEqual(set(groups), {'', 'main'})


class CaptureBatchTests(unittest.TestCase):
    def run_batch(self, callback=None, target='knowledge'):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / 'worldbooks').mkdir()
        for name in ('main', 'knowledge'):
            save_worldbook_atomic(root / 'worldbooks' / f'{name}.yml', {'name': name, 'entries': []})
        candidate = {'operation': 'add', 'target_book_id': target, 'name': '蓝雨',
                     'content': '降雨为蓝色', 'scope': 'natural_law', 'risk': 'low', 'confidence': 'high'}
        class AI:
            calls = 0
            def chat_json(self, *args, **kwargs):
                self.calls += 1
                if callback:
                    callback(root)
                return json.dumps({'candidates': [candidate]}), None
        ai = AI()
        result = capture_books(WorldbookCaptureService(ai), root, '行动', '蓝雨持续', review_all=False)
        return root, ai, result

    def test_one_request_writes_selected_book_not_first_book(self):
        root, ai, result = self.run_batch(target='main')
        self.assertEqual(ai.calls, 1)
        self.assertEqual(len(result['books']['main']['added']), 1)
        other = yaml.safe_load((root / 'worldbooks/knowledge.yml').read_text(encoding='utf-8'))
        self.assertEqual(other['entries'], [])

    def test_manual_edit_during_request_is_preserved(self):
        def edit(root):
            save_worldbook_atomic(root / 'worldbooks/knowledge.yml', {'name': 'manual', 'entries': []})
        root, ai, result = self.run_batch(edit)
        self.assertTrue(result['skipped'])
        saved = yaml.safe_load((root / 'worldbooks/knowledge.yml').read_text(encoding='utf-8'))
        self.assertEqual(saved['name'], 'manual')
        self.assertEqual(saved['entries'], [])

    def test_primary_change_discards_results(self):
        def edit(root):
            (root / 'session_state.json').write_text(json.dumps({'worldbook_collaboration': {'primary_book': 'main'}}), encoding='utf-8')
        _, _, result = self.run_batch(edit)
        self.assertEqual(result['books'], {})
        self.assertTrue(result['skipped'])

    def test_uncertain_addition_creates_local_fallback(self):
        _, ai, result = self.run_batch(target='')
        self.assertEqual(ai.calls, 1)
        self.assertIn('_本局自动设定', result['books'])

    def test_disabled_fallback_not_reenabled(self):
        def disable(root):
            save_worldbook_atomic(root / 'worldbooks/auto.yml', {
                'name': '自动书', 'entries': [], 'is_auto_capture_book': True, 'is_active': False})
        root, _, result = self.run_batch(disable, target='')
        self.assertEqual(result['books'], {})
        self.assertTrue(result['skipped'])
        self.assertFalse(yaml.safe_load((root / 'worldbooks/auto.yml').read_text(encoding='utf-8'))['is_active'])
