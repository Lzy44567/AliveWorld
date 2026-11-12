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
    def test_npc_organize_and_rewound_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            record = {'id': 'npc-1', 'name': '林', 'aliases': ['路人', '林']}
            game = SimpleNamespace(save_dir_path=str(root / 'story'),
                state_mgr=SimpleNamespace(npc_presence=SimpleNamespace(identities=SimpleNamespace(records={'npc-1': record}))),
                history={'story_turns': [{'turn_id': 1, 'player': '你好', 'story': '她介绍自己叫林。', 'private': '秘密'}]})
            app = FastAPI(); app.include_router(routes.router)
            result = {'profile': {'description': '谨慎的旅人'}, 'experiences': '记得初次见面', 'notes': '请确认'}
            with patch.dict(routes.active_sessions, {'npc-test': game}), \
                    patch.object(routes, 'PATHS', SimpleNamespace(data_dir=root / 'global')), \
                    patch.object(routes, 'get_task_engine', return_value=object()), \
                    patch.object(routes, 'extract_character', return_value=result) as extract:
                client = TestClient(app)
                url = '/npc-test/character-extraction/npc:npc-1'
                request = {'turn_ids': [1], 'acknowledged': True}
                self.assertEqual(400, client.post(url + '/organize', json={**request, 'acknowledged': False}).status_code)
                extract.assert_not_called()
                draft = client.post(url + '/organize', json=request).json()
                self.assertEqual(['路人', '林'], extract.call_args.kwargs['subject']['aliases'])
                self.assertNotIn('private', extract.call_args.kwargs['evidence'][0])
                body = dict(name='旅行者', profile=draft['profile'], expected_revision=draft['revision'],
                    reviewed=True, include_experiences=True, experiences=draft['experiences'],
                    evidence_turn_ids=draft['evidence_turn_ids'], evidence_revision=draft['evidence_revision'])
                game.history['story_turns'][0]['story'] = '修改过的回合'
                self.assertEqual(409, client.post(url, json=body).status_code)
                game.history['story_turns'] = []
                self.assertEqual(400, client.post(url, json=body).status_code)
                self.assertFalse((root / 'global').exists())

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
