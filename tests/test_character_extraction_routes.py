import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.v1 import character_extraction_routes as routes


class ExtractionRouteTests(unittest.TestCase):
    def test_preview_save_conflict_and_source_unchanged(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / 'story' / 'characters' / 'original.yml'
            source.parent.mkdir(parents=True)
            source.write_text(yaml.safe_dump({'name': '原角色', 'description': '稳定人设',
                'memories': ['不应自动分享']}, allow_unicode=True), encoding='utf-8')
            original = source.read_bytes()
            app = FastAPI(); app.include_router(routes.router)
            with patch.dict(routes.active_sessions, {'test': SimpleNamespace(save_dir_path=str(root / 'story'))}), \
                    patch.object(routes, 'PATHS', SimpleNamespace(data_dir=root / 'global')):
                client = TestClient(app)
                url = '/test/character-extraction/原角色'
                preview = client.get(url)
                self.assertEqual(200, preview.status_code)
                value = preview.json()
                self.assertNotIn('memories', value['profile'])
                body = dict(name='独立卡', profile=value['profile'], expected_revision=value['revision'], reviewed=True)
                self.assertEqual(400, client.post(url, json={**body, 'reviewed': False}).status_code)
                self.assertEqual(200, client.post(url, json=body).status_code)
                self.assertEqual(409, client.post(url, json=body).status_code)
                saved = yaml.safe_load((root / 'global' / 'characters' / '独立卡.yml').read_text(encoding='utf-8'))
                self.assertEqual('稳定人设', saved['description'])
                self.assertEqual(original, source.read_bytes())
                source.write_text('name: 原角色\ndescription: 新内容', encoding='utf-8')
                self.assertEqual(409, client.post(url, json={**body, 'name': '另一个'}).status_code)
