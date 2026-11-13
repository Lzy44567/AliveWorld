import tempfile
import unittest
from pathlib import Path
import yaml
from core.manuscript_project import ManuscriptProjects
from core.manuscript_publish import publish_candidates


class PublishTests(unittest.TestCase):
    def test_review_publish_conflict_future_isolation_and_retry(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            repo = ManuscriptProjects(root / 'projects')
            project = repo.create('稿', '原文')
            candidates = [dict(kind=kind, name=name, origin='original', source_quote='原文', content=content)
                for kind, name, content in [('characters','林',{'description':'学生'}),
                    ('styles','短句',{'content':'简洁'}), ('future_notes','觉醒',{'text':'未来觉醒'})]]
            project = repo.store_analysis(project['id'],0,'原文',candidates,'')
            ids = [c['id'] for c in project['candidates']]
            project = repo.review(project['id'],1,[{'id':i,'status':'accepted'} for i in ids])
            directory = root / 'assets' / 'styles'; directory.mkdir(parents=True)
            (directory/'短句.yml').write_text('name: 短句\ncontent: 原资产',encoding='utf-8')
            result = publish_candidates(repo,root/'assets',project['id'],2,ids)
            self.assertEqual(['published','error','project_only'],[r['status'] for r in result['results']])
            self.assertFalse((root/'assets'/'future_notes').exists())
            self.assertEqual('原资产',yaml.safe_load((directory/'短句.yml').read_text(encoding='utf-8'))['content'])
            project = repo.review(project['id'],result['project']['revision'],[{'id':ids[1],'name':'新短句'}])
            retry = publish_candidates(repo,root/'assets',project['id'],project['revision'],ids)
            self.assertEqual(['published','published','project_only'],[r['status'] for r in retry['results']])
            self.assertEqual(1,len(list((root/'assets'/'characters').glob('*.yml'))))
