import tempfile
import unittest
from pathlib import Path
from core.manuscript_project import ManuscriptProjects


class ManuscriptTests(unittest.TestCase):
    def test_source_draft_and_future_material_persist_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = ManuscriptProjects(directory)
            project = repo.create('测试手稿', '林是一名学生。未来抵达灯塔后觉醒。')
            items = [dict(kind='characters', name='林', origin='original',
                          source_quote='林是一名学生。', content={'description': '学生'}),
                     dict(kind='future_notes', name='觉醒节点', origin='original',
                          source_quote='未来抵达灯塔后觉醒。', content={'text': '抵达灯塔后觉醒'})]
            saved = repo.store_analysis(project['id'], 0, project['source_text'], items, '节点尚未执行')
            loaded = ManuscriptProjects(directory).load(project['id'])
            self.assertEqual(saved, loaded)
            self.assertNotIn('觉醒', loaded['candidates'][0]['content']['description'])
            self.assertEqual('future_notes', loaded['candidates'][1]['kind'])
            self.assertEqual(project['source_text'], loaded['source_text'])
            self.assertEqual(1, len(repo.list()))
            with self.assertRaises(ValueError):
                repo.store_analysis(project['id'], 0, project['source_text'], items, '')
            self.assertEqual(2, len(repo.load(project['id'])['candidates']))

    def test_bad_model_source_preserves_existing_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = ManuscriptProjects(directory)
            project = repo.create('原稿', '真实原文')
            before = next(Path(directory).glob('*.yml')).read_bytes()
            with self.assertRaises(ValueError):
                repo.store_analysis(project['id'], 0, '真实原文', [dict(kind='characters',
                    name='甲', origin='original', source_quote='捏造引用', content={})], '')
            self.assertEqual(before, next(Path(directory).glob('*.yml')).read_bytes())
            with self.assertRaises(ValueError):
                repo.load('../outside')
