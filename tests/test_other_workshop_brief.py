import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.asset_workshop import AssetWorkshop
from core.asset_workshop_agent import AssetWorkshopAgent
from core.preference_workshop import PreferenceWorkshop
from core.preference_workshop_agent import PreferenceWorkshopAgent
from api.v1 import asset_workshop_routes as assets, preference_workshop_routes as prefs


class Engine:
    def __init__(self):
        self.calls = []
    def chat_json(self, system, prompt, **kwargs):
        self.calls.append(prompt)
        return json.dumps({'message': 'ok', 'creative_brief': '玩家明确目标', 'operations': []}), None


class OtherWorkshopBriefTests(unittest.TestCase):
    def test_asset_first_summary_manual_clear_and_old_session(self):
        for kind in ['characters', 'styles', 'entities']:
            with self.subTest(kind=kind):
                workshop = AssetWorkshop('test', kind, Path('unused.yml'), {'name': 'test'})
                engine = Engine()
                agent = AssetWorkshopAgent(engine)
                agent.respond(workshop, '玩家明确目标', 'refine')
                self.assertEqual(workshop.creative_brief, '玩家明确目标')
                workshop.messages = [{'role': 'user', 'content': 'later'}] * 30
                agent.respond(workshop, 'continue', 'refine')
                self.assertIn('玩家明确目标', engine.calls[-1])
                self.assertEqual(len(engine.calls), 2)
                workshop.set_creative_brief('  手填目标  ')
                restored = AssetWorkshop.from_dict(workshop.to_dict())
                self.assertEqual(restored.creative_brief, '手填目标')
                restored.set_creative_brief('')
                agent.respond(restored, 'continue', 'refine')
                self.assertEqual(restored.creative_brief, '')
                legacy = workshop.to_dict()
                legacy.pop('creative_brief')
                legacy.pop('brief_edited')
                self.assertEqual(AssetWorkshop.from_dict(legacy).creative_brief, '')
                self.assertNotIn('creative_brief', workshop.draft)

    def test_preference_does_not_extract_model_brief_or_sensitive_evidence(self):
        workshop = PreferenceWorkshop('test', {'preferences': []})
        engine = Engine()
        agent = PreferenceWorkshopAgent(engine)
        agent.respond(workshop, '讨论', 'discover', [{'sensitive': True, 'summary': 'SECRET_EVIDENCE'}])
        self.assertEqual(workshop.creative_brief, '')
        self.assertNotIn('SECRET_EVIDENCE', engine.calls[-1])
        workshop.set_creative_brief('手动限定话题')
        restored = PreferenceWorkshop.from_dict(workshop.to_dict())
        restored.messages = [{'role': 'user', 'content': 'later'}] * 30
        agent.respond(restored, '继续', 'discover', [])
        self.assertIn('手动限定话题', engine.calls[-1])
        self.assertEqual(restored.draft, [])

    def test_http_save_and_failure_all_types(self):
        for kind in ['characters', 'styles', 'entities', 'preferences']:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                workshop = PreferenceWorkshop('test', {'preferences': []}) if kind == 'preferences' else AssetWorkshop('test', kind, Path(directory) / 'asset.yml', {'name': 'test'})
                routes = prefs if kind == 'preferences' else assets
                loader = 'load_preference_workshop' if kind == 'preferences' else 'load_asset_workshop'
                app = FastAPI()
                app.include_router(routes.router)
                with patch.object(routes, loader, return_value=workshop), patch.object(routes, 'WORKSHOP_DIR', Path(directory)), TestClient(app, raise_server_exceptions=False) as client:
                    response = client.put('/test/creative-brief', json={'creative_brief': '  目标  '})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()['creative_brief'], '目标')
                    self.assertEqual(json.loads((Path(directory) / 'test.json').read_text(encoding='utf-8'))['creative_brief'], '目标')
                    self.assertEqual(client.put('/test/creative-brief', json={'creative_brief': 'x' * 2001}).status_code, 422)
                    before = copy.deepcopy(workshop.to_dict())
                    with patch.object(type(workshop), 'save_session', side_effect=OSError('disk full')):
                        self.assertEqual(client.put('/test/creative-brief', json={'creative_brief': 'other'}).status_code, 500)
                    self.assertEqual(workshop.to_dict(), before)
                    workshop.published = True
                    self.assertEqual(client.put('/test/creative-brief', json={'creative_brief': 'other'}).status_code, 400)
