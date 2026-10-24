import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from api.v1 import generation_routes as routes
from core.generation_control import GenerationCancelled
from core.generation_recovery import capture_generation, capture_response, public_text, read_drafts, save_draft
from core.json_stream import STORY_FIELDS, WORKSHOP_FIELDS


class RecoveryTests(unittest.TestCase):
    def test_provider_stream_and_nonstream_preserve_only_public_text(self):
        from tests.test_streaming import stream_engine, chunk
        from core.ai_engine import AIEngine
        from tests.test_ai_engine import completion
        for streaming in (False, True):
            for reason in ('length', 'content_filter'):
                with self.subTest(streaming=streaming, reason=reason), capture_generation() as captured:
                    raw = '{"story_text":"可读正文'
                    if streaming:
                        engine, _, _, _ = stream_engine([chunk(raw), chunk(reason=reason)])
                    else:
                        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: completion(raw, reason))))
                        with patch('core.ai_engine.OpenAI', return_value=client):
                            engine = AIEngine({'api_key': 'fake', 'base_url': 'http://localhost', 'model': 'fake'})
                    result, error = engine.chat_json('中性测试', 'test', **({'on_text_delta': lambda text: None} if streaming else {}))
                    self.assertFalse(result)
                    self.assertTrue(error)
                    self.assertEqual(captured['text'], '' if reason == 'content_filter' else '可读正文')

    def test_threads_do_not_share_capture(self):
        import threading
        barrier = threading.Barrier(2)
        def run(text):
            with capture_generation() as state:
                capture_response(json.dumps({'story_text': text}), STORY_FIELDS)
                barrier.wait(timeout=5)
                return state['text']
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(list(pool.map(run, ['one', 'two'])), ['one', 'two'])

    def test_owner_restart_and_workshop_target_isolation(self):
        from api.v1.recovery_access import recovery_directories
        from core import worldbook_workshop_registry as worlds, asset_workshop_registry as assets, preference_workshop_registry as preferences
        from core.session_manager import active_sessions
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            with patch.object(worlds, 'WORKSHOP_DIR', root / 'worlds'), patch.object(assets, 'WORKSHOP_DIR', root / 'assets'), patch.object(preferences, 'WORKSHOP_DIR', root / 'preferences'):
                worlds.WORKSHOP_DIR.mkdir()
                for identity, target in [('old', 'same.yml'), ('new', 'same.yml'), ('other', 'other.yml')]:
                    (worlds.WORKSHOP_DIR / f'{identity}.json').write_text(json.dumps({'id': identity, 'target_path': str(root / target)}), encoding='utf-8')
                current, related = recovery_directories('workshop', 'new')
                self.assertEqual(current.name, 'new')
                self.assertEqual({p.name for p in related}, {'old', 'new'})
                with self.assertRaises(HTTPException): recovery_directories('workshop', '../escape')
                with patch.dict(active_sessions, {'session-new': SimpleNamespace(save_dir_path=str(root / 'save'))}):
                    current, related = recovery_directories('story', 'session-new')
                    save_draft(current, uuid4(), {'text': '持久正文', 'reason': 'length', 'blocked': False}, 'request', 'send', '')
                with patch.dict(active_sessions, {'after-restart': SimpleNamespace(save_dir_path=str(root / 'save'))}):
                    self.assertEqual(read_drafts(recovery_directories('story', 'after-restart')[1])[0]['text'], '持久正文')

    def test_storage_failure_is_explicit_not_success(self):
        @routes.controlled_generation('story')
        def generate(identity, payload):
            capture_response('{"story_text":"已生成"}', STORY_FIELDS)
            raise ValueError('JSON broken')
        with patch.object(routes, 'recovery_directories', return_value=(Path('unused'), [])), patch.object(routes, 'save_draft', side_effect=OSError('disk full')):
            with self.assertRaises(HTTPException) as raised:
                generate('s', SimpleNamespace(generation_id=uuid4(), action='x'))
            self.assertIn('残稿保存也失败', raised.exception.detail)

    def test_only_public_strings_survive_partial_and_broken_json(self):
        for source in ['{"story_text":"可读正文', '{"story_text":"可读正文",bad',
                       '```json\n{"story_text":"可读正文',
                       '{"secret":{"story_text":"不公开"},"story_text":"可读正文']:
            self.assertEqual(public_text(source, STORY_FIELDS), '可读正文')
        self.assertEqual(public_text('{"numeric_changes":{"hp":10},"reasoning":"隐私"}', STORY_FIELDS), '')
        self.assertIn('结论\n可读说明', public_text('{"message":"可读说明","operations":[', WORKSHOP_FIELDS))

    def test_filter_blocks_capture_and_nested_scopes_are_isolated(self):
        with capture_generation() as outer:
            capture_response('{"story_text":"外层"}', STORY_FIELDS)
            with capture_generation() as inner:
                capture_response('{"story_text":"内层"}', STORY_FIELDS)
                capture_response('', STORY_FIELDS, 'content_filter')
                capture_response('{"story_text":"不应恢复"}', STORY_FIELDS)
            self.assertEqual(outer['text'], '外层')
            self.assertTrue(inner['blocked'])
            self.assertEqual(inner['text'], '')

    def test_atomic_independent_files_and_no_raw_error_saved(self):
        with tempfile.TemporaryDirectory() as root:
            state = {'text': '可读正文', 'reason': 'length', 'blocked': False}
            save_draft(root, uuid4(), state, '原请求', '_process_turn', 'private-provider-detail')
            save_draft(root, uuid4(), state, '第二请求', '_process_turn', 'private-provider-detail')
            records = read_drafts([root])
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]['reason'], 'output_limit')
            self.assertNotIn('private-provider', json.dumps(records))
            self.assertFalse(list(Path(root).glob('*.tmp')))

    def test_generation_boundary_failure_success_cancel_and_delete(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / 'recovery'
            @routes.controlled_generation('story')
            def generate(identity, payload):
                capture_response('{"story_text":"部分内容', STORY_FIELDS, 'length')
                if payload.action == 'cancel':
                    raise GenerationCancelled('取消')
                if payload.action == 'filter':
                    capture_response('', STORY_FIELDS, 'content_filter')
                if payload.action != 'success':
                    raise HTTPException(502, 'length: incomplete')
                return {'ok': True}
            with patch.object(routes, 'recovery_directories', return_value=(directory, [directory])):
                for action in ['fail', 'success', 'cancel', 'filter']:
                    payload = SimpleNamespace(generation_id=uuid4(), action=action)
                    if action == 'success':
                        self.assertTrue(generate('session', payload)['ok'])
                    else:
                        with self.assertRaises(HTTPException):
                            generate('session', payload)
                app = FastAPI()
                app.include_router(routes.router)
                with TestClient(app) as client:
                    result = client.get('/story/session/recovery')
                    self.assertEqual(result.status_code, 200)
                    records = result.json()['drafts']
                    self.assertEqual(len(records), 1)
                    self.assertEqual(records[0]['request'], 'fail')
                    self.assertEqual(client.delete(f"/story/session/recovery/{records[0]['id']}").status_code, 200)
                    self.assertEqual(client.get('/story/session/recovery').json()['drafts'], [])


if __name__ == '__main__':
    unittest.main()
