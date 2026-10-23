import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.worldbook_extraction import extraction_view, prepare_extraction, save_extraction, ExtractionConflict
from core.worldbook_revisions import record_capture_changes
from core.worldbook_collaboration import default_collaboration, rule_catalog, collect_conflicts
from core.session_manager import mutation_guard, save_identity
from core.world_packages.authoring import WorldPackageAuthoringService, AssetSelection
from api.v1 import world_package_routes as routes


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.story = self.root / 'private_story'
        (self.story / 'worldbooks').mkdir(parents=True)
        self.source = self.story / 'worldbooks/book.yml'
        self.book = {'name': '原书', 'overview': '世界概述', 'axioms': ['世界公理'],
                     'capture_reviews': ['私人审阅'], '_aliveworld': {'source_save': '私人存档'},
                     'entries': [{'id': 'a', 'name': '规则', 'keys': '城市', 'content': '有效内容'},
                                 {'id': 'p', 'name': '待审', 'content': '不要带出', 'tags': ['待确认']},
                                 {'id': 'off', 'name': '停用', 'content': '不要带出', 'is_active': False}]}
        self.source.write_text(yaml.safe_dump(self.book, allow_unicode=True), encoding='utf-8')
        self.state = default_collaboration()
        self.authoring = WorldPackageAuthoringService(self.root / 'global')

    def view(self, turns=None):
        return extraction_view(self.story, turns or [], self.state)

    def prepare(self, view=None, **changes):
        view = view or self.view()
        options = dict(book_id='book', expected_revision=view['revision'], name='新书', entry_ids=['a'], include_overview=True, include_axioms=True)
        options.update(changes)
        return prepare_extraction(view, **options)

    def test_projection_and_export_are_independent_and_clean(self):
        original = self.source.read_bytes()
        view = self.view()
        self.assertEqual(view['books'][0]['excluded_count'], 2)
        book = self.prepare(view)
        self.assertNotEqual(book['entries'][0]['id'], 'a')
        self.assertNotIn('私人', json.dumps(book, ensure_ascii=False))
        save_extraction(self.authoring.data_root / 'worldbooks', book)
        target, _ = self.authoring.export(metadata={'name': '作品', 'author': '测试'}, selections=[AssetSelection('worldbooks', '新书')])
        with zipfile.ZipFile(target) as archive:
            combined = '\n'.join(archive.read(n).decode('utf-8') for n in archive.namelist())
        self.assertIn('有效内容', combined)
        for text in ('不要带出', '私人', 'capture_history', 'capture_reviews', 'source_save'):
            self.assertNotIn(text, combined)
        self.assertEqual(self.source.read_bytes(), original)
        with self.assertRaises(ExtractionConflict): save_extraction(self.authoring.data_root / 'worldbooks', book)

    def test_rollback_and_changed_preview(self):
        turn = {'turn_id': 1, 'player': '新增', 'story': '新规则'}
        after = {**self.book, 'entries': [*self.book['entries'], {'id': 'new', 'name': '新', 'content': '新'}]}
        self.source.write_text(yaml.safe_dump(record_capture_changes(self.book, after, turn)), encoding='utf-8')
        view = self.view([turn])
        self.assertEqual(len(view['books'][0]['entries']), 2)
        reverted = self.view()
        self.assertEqual(len(reverted['books'][0]['entries']), 1)
        with self.assertRaises(ExtractionConflict): self.prepare(reverted, expected_revision=view['revision'])

    def test_selection_and_privacy_gate(self):
        for changes in ({'entry_ids': ['p']}, {'entry_ids': ['a', 'a']}, {'entry_ids': [], 'include_overview': False, 'include_axioms': False}, {'name': '../bad'}):
            with self.assertRaises(ValueError): self.prepare(**changes)
        view = self.view(); view['books'][0]['overview'] = 'api_key: sk-abcdefghijklmnopqrstuv'
        with self.assertRaises(ValueError): self.prepare(view)
        self.assertEqual(self.prepare(view, include_overview=False)['overview'], '')

    def test_conflict_disabled_entry_not_exported(self):
        primary = {'name': '主书', 'overview': '只允许魔法', 'entries': []}
        (self.story / 'worldbooks/main.yml').write_text(yaml.safe_dump(primary), encoding='utf-8')
        from core.worldbook_collaboration import load_books
        turn = {'turn_id': 1, 'player': '行动', 'story': '事实'}
        books = load_books(self.story, [turn]); rules = rule_catalog(books)
        keep = next(r for r in rules.values() if r['book_id'] == 'main')
        disable = next(r for r in rules.values() if r['item_id'] == 'a')
        self.state['primary_book'] = 'main'
        self.state, _ = collect_conflicts([{'keep': keep['ref'], 'disable': disable['ref'], 'keep_quote': keep['content'], 'disable_quote': disable['content'], 'scope': '同世界', 'reason': '矛盾'}], state=self.state, books=books, supplied_rules=rules, source_turn=turn)
        self.assertEqual(next(b for b in self.view([turn])['books'] if b['book_id'] == 'book')['entries'], [])

    def test_http_requires_review_and_detects_stale_preview(self):
        app = FastAPI(); app.include_router(routes.router, prefix='/packages')
        game = SimpleNamespace(save_dir_path=str(self.story), history={'story_turns': []}, worldbook_collaboration=self.state)
        with patch.dict(routes.active_sessions, {'story': game}, clear=True), patch.object(routes, 'AUTHORING', self.authoring):
            client = TestClient(app); base = '/packages/authoring/stories/story/worldbooks'
            view = client.get(base).json()
            data = dict(book_id='book', expected_revision=view['revision'], name='新书', entry_ids=['a'])
            self.assertEqual(client.post(base, json=data).status_code, 400)
            data['reviewed'] = True
            self.assertEqual(client.post(base, json=data).status_code, 200)
            self.assertEqual(client.post(base, json=data).status_code, 409)
            game.history['story_turns'] = [{'turn_id': 2, 'story': '发生变化'}]
            data['name'] = '另一书'
            self.assertEqual(client.post(base, json=data).status_code, 409)
            self.assertFalse((self.authoring.data_root / 'worldbooks/另一书.yml').exists())
            with mutation_guard('story', save_identity(self.story)):
                self.assertEqual(client.get(base).status_code, 409)

    def test_failed_write_leaves_source_and_destination_unchanged(self):
        original = self.source.read_bytes()
        book = self.prepare()
        with patch('core.worldbook_extraction.save_worldbook_atomic', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): save_extraction(self.authoring.data_root / 'worldbooks', book)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertFalse((self.authoring.data_root / 'worldbooks/新书.yml').exists())
