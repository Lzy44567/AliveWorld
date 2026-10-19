import copy
import json
import unittest
import tempfile
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pathlib import Path
from types import SimpleNamespace

from core.workshop_context import conversation_context
from core.worldbook_workshop import WorldbookWorkshop
from core.worldbook_workshop_agent import WorldbookWorkshopAgent
from core.asset_workshop import AssetWorkshop
from core.asset_workshop_agent import AssetWorkshopAgent
from core.preference_workshop import PreferenceWorkshop
from core.preference_workshop_agent import PreferenceWorkshopAgent
from api.v1.worldbook_workshop_routes import WorkshopChatRequest
from api.v1.asset_workshop_routes import ChatPayload as AssetChat
from api.v1.preference_workshop_routes import ChatPayload as PreferenceChat
from api.v1 import preference_workshop_routes as preferences
from core.workshop_history import published_history


class Engine:
    def __init__(self):
        self.calls = []

    def chat_json(self, system, prompt, **kwargs):
        self.calls.append(prompt)
        return json.dumps({'message': '继续讨论', 'operations': []}), None


class WorkshopContextTests(unittest.TestCase):
    def test_bounded_retrieval_preserves_original_and_old_relevant_excerpt(self):
        history = [{'workshop_id': 'old', 'messages': [
            {'role': 'user', 'content': '旧决定：蓝晶矿只能在雨夜开采'},
            {'role': 'assistant', 'content': '提案：炸毁矿井，尚未确认'},
        ] + [{'role': 'user', 'content': '无关议题' * 1000}] * 80}]
        workshop = SimpleNamespace(id='now', messages=[{'role': 'user', 'content': '近期讨论' * 900}] * 20)
        before = copy.deepcopy(history)
        text, info = conversation_context(workshop, '继续蓝晶矿的雨夜开采设计', history)
        self.assertIn('蓝晶矿只能在雨夜开采', text)
        self.assertIn('old:1', info['selected_sources'])
        self.assertIn('旧讨论可能被后来决定取代', text)
        self.assertLess(len(text), 16500)
        self.assertEqual(history, before)

    def test_all_agents_use_history_without_extra_model_call(self):
        history = [{'workshop_id': 'checkpoint', 'messages': [{'role': 'user', 'content': '蓝晶矿设定只在雨夜生效'}]}]
        pairs = [(WorldbookWorkshop('book', Path('unused.yml'), {'name': '书'}), WorldbookWorkshopAgent, 'expand')]
        pairs += [(AssetWorkshop(kind, kind, Path('unused.yml'), {'name': '卡'}), AssetWorkshopAgent, 'refine')
                  for kind in ('characters', 'styles', 'entities')]
        pairs += [(PreferenceWorkshop('pref', {'preferences': []}), PreferenceWorkshopAgent, 'discover')]
        for workshop, agent, mode in pairs:
            with self.subTest(agent=agent, mode=mode):
                engine = Engine()
                args = [workshop, '继续蓝晶矿', mode]
                if mode == 'discover':
                    args.append([])
                result = agent(engine).respond(*args, history=history)
                self.assertEqual(len(engine.calls), 1)
                self.assertIn('蓝晶矿设定只在雨夜生效', engine.calls[0])
                self.assertEqual(result['context_info']['excerpt_count'], 1)
                self.assertEqual(len(workshop.messages), 2)
                self.assertNotIn('checkpoint', json.dumps(workshop.to_dict(), ensure_ascii=False))

    def test_preference_opt_in_and_no_history_when_disabled(self):
        self.assertFalse(PreferenceChat(message='继续').use_history)
        self.assertTrue(AssetChat(message='继续').use_history)
        self.assertTrue(WorkshopChatRequest(message='继续').use_history)
        text, info = conversation_context(SimpleNamespace(id='new', messages=[]), '继续')
        self.assertEqual(info['available_messages'], 0)
        self.assertNotIn('旧秘密', text)

    def test_http_preference_history_requires_explicit_opt_in(self):
        workshop = PreferenceWorkshop('privacy', {'preferences': []})
        history = [{'workshop_id': 'old', 'messages': [{'role': 'user', 'content': 'PRIVATE_OLD_DISCUSSION'}]}]
        engine = Engine()
        app = FastAPI()
        app.include_router(preferences.router)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(preferences, 'WORKSHOP_DIR', Path(directory)), \
             patch.object(preferences, 'load_preference_workshop', return_value=workshop), \
             patch.object(preferences, '_engine', return_value=engine), \
             patch.object(preferences.repository, 'load', return_value={'preferences': [], 'evidence': []}), \
             patch.object(preferences, 'list_preference_workshop_history', return_value=history) as history_loader, \
             TestClient(app) as client:
            first = client.post('/privacy/chat', json={'message': '继续'})
            self.assertEqual(first.status_code, 200, first.text)
            history_loader.assert_not_called()
            self.assertNotIn('PRIVATE_OLD_DISCUSSION', engine.calls[-1])
            second = client.post('/privacy/chat', json={'message': '继续', 'use_history': True})
            self.assertEqual(second.status_code, 200, second.text)
            history_loader.assert_called_once()
            self.assertIn('PRIVATE_OLD_DISCUSSION', engine.calls[-1])
            self.assertEqual(len(engine.calls), 2)

    def test_same_name_different_target_does_not_mix_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sessions = {}
            for name in ['global', 'local']:
                workshop = WorldbookWorkshop(name, root / name / 'same.yml', {'name': 'same'})
                workshop.published = True
                workshop.messages = [{'role': 'user', 'content': name}]
                workshop.save_session(root / 'sessions')
                sessions[name] = workshop
            result = published_history(root / 'sessions', sessions.get,
                                       lambda item: item.target_path == root / 'local' / 'same.yml')
            self.assertEqual([item['workshop_id'] for item in result], ['local'])


if __name__ == '__main__':
    unittest.main()
