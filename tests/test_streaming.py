import asyncio
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

from api.v1 import game_routes, asset_workshop_routes, preference_workshop_routes, worldbook_workshop_routes
from api.v1.streaming import stream_response, workshop_stream_response
from core.ai_engine import AIEngine
from core.asset_workshop import AssetWorkshop
from core.json_stream import JSONTextPreview, STORY_FIELDS, WORKSHOP_FIELDS, PREFERENCE_FIELDS
from core.preference_workshop import PreferenceWorkshop
from core.session_manager import mutation_guard, register_session, unregister_session
from core.worldbook_workshop import WorldbookWorkshop


def chunk(content=None, reason=None, *, reasoning="hidden reasoning", tools=None, usage=None):
    return SimpleNamespace(id="stream-test", choices=[SimpleNamespace(
        index=0, finish_reason=reason,
        delta=SimpleNamespace(content=content, reasoning_content=reasoning, tool_calls=tools),
    )], usage=usage)


class FakeStream:
    def __init__(self, chunks):
        self.chunks = chunks
        self.closed = False

    def __iter__(self):
        yield from self.chunks

    def close(self):
        self.closed = True


def stream_engine(chunks):
    stream = FakeStream(chunks)
    create = Mock(return_value=stream)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client.with_options = Mock(return_value=client)
    with patch("core.ai_engine.OpenAI", return_value=client):
        engine = AIEngine({"api_key": "test", "base_url": "http://localhost", "model": "test"})
    return engine, stream, create, client


def decode_event(value):
    lines = value.splitlines()
    return lines[0].split(": ", 1)[1], json.loads(lines[1].split(": ", 1)[1])


async def collect(response):
    return [decode_event(value) async for value in response.body_iterator]


class JSONPreviewTests(unittest.TestCase):
    def render(self, raw, fields=STORY_FIELDS, width=1):
        output = []
        preview = JSONTextPreview(fields, output.append)
        for index in range(0, len(raw), width):
            preview.feed(raw[index:index + width])
        return "".join(output)

    def test_every_character_boundary_decodes_escapes_and_unicode(self):
        raw = '{"secret":{"story_text":"nested secret"},"story_text":"中文\\n\\\"引号\\\"\\\\路径\\u4f60\\ud83d\\ude00"}'
        self.assertEqual(self.render(raw), '中文\n"引号"\\路径你😀')

    def test_visible_text_arrives_before_json_finishes(self):
        output = []
        preview = JSONTextPreview(STORY_FIELDS, output.append)
        preview.feed('{"story_text":"先到达')
        self.assertEqual(output, ['先到达'])
        preview.feed('的正文","status_updates":{"secret":"状态"}}')
        self.assertEqual(''.join(output), '先到达的正文')

    def test_workshop_sections_only_direct_public_strings_and_four_notes(self):
        raw = json.dumps({
            "operations": [{"message": "秘密操作", "changes": {"understanding": "秘密状态"}}],
            "understanding": "目标", "design_notes": ["一", "二", "三", "四", "不显示"],
            "message": "结论", "suggested_actions": ["不显示建议"],
        }, ensure_ascii=False)
        text = self.render(raw, WORKSHOP_FIELDS)
        self.assertEqual(text, '理解\n目标\n\n设计依据\n1. 一\n2. 二\n3. 三\n4. 四\n\n结论\n结论')
        self.assertNotIn('秘密', text)
        self.assertNotIn('不显示', text)

    def test_preference_explanations_have_their_own_heading(self):
        self.assertEqual(self.render('{"alternative_explanations":["另一解释"]}', PREFERENCE_FIELDS),
                         '仍需保留的其他解释\n1. 另一解释')

    def test_wrong_type_does_not_project_nested_values(self):
        self.assertEqual(self.render('{"story_text":["不应显示"]}'), '')
        self.assertEqual(self.render('{"message":{"message":"不应显示"}}', WORKSHOP_FIELDS), '')

    def test_duplicate_field_cannot_replace_already_visible_prose(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.render('{"story_text":"一","story_text":"二"}')

    def test_invalid_escape_and_unpaired_surrogate_fail(self):
        for raw in ('{"story_text":"\\x"}', '{"story_text":"\\ud83dA"}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.render(raw)


class ProviderStreamingTests(unittest.TestCase):
    def test_real_sdk_stream_single_call_only_content_and_keep_budget(self):
        engine, stream, create, client = stream_engine([
            chunk('{"story_text":"可见'), chunk('正文","state":{"secret":"hidden"}}'),
            chunk(reason="stop", usage={"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11}),
        ])
        output = []
        raw, error = engine.chat_json('JSON', 'test', max_tokens=400, on_text_delta=output.append)
        self.assertIsNone(error)
        self.assertEqual(json.loads(raw)['story_text'], '可见正文')
        self.assertEqual(''.join(output), '可见正文')
        self.assertEqual(create.call_count, 1)
        self.assertTrue(create.call_args.kwargs['stream'])
        self.assertEqual(create.call_args.kwargs['max_tokens'], 400)
        client.with_options.assert_called_once_with(max_retries=0, timeout=120.0)
        self.assertTrue(stream.closed)

    def test_length_filter_missing_finish_blank_and_malformed_are_not_committed_or_retried(self):
        cases = [
            [chunk('{"story_text":"残片"}', 'length')],
            [chunk('{"story_text":"残片"}', 'content_filter')],
            [chunk('{"story_text":"残片"}')],
            [chunk('   ', 'stop')],
            [chunk('{"story_text":"残片"', 'stop')],
        ]
        for chunks in cases:
            with self.subTest(chunks=chunks):
                engine, stream, create, _ = stream_engine(chunks)
                raw, error = engine.chat_json('JSON', 'test', on_text_delta=lambda _: None)
                self.assertEqual(raw, '')
                self.assertTrue(error)
                self.assertEqual(create.call_count, 1)
                self.assertTrue(stream.closed)

    def test_stream_exception_closes_provider_and_no_second_request(self):
        def broken():
            yield chunk('{"story_text":"已看到')
            raise TimeoutError('provider disconnected')
        engine, stream, create, _ = stream_engine(broken())
        raw, error = engine.chat_json('JSON', 'test', on_text_delta=lambda _: None)
        self.assertEqual(raw, '')
        self.assertIn('disconnected', error)
        self.assertEqual(create.call_count, 1)
        self.assertTrue(stream.closed)

    def test_budget_failure_calls_no_provider(self):
        engine, _, create, client = stream_engine([])
        engine.budget_options = {"context_window": 8192, "max_output_tokens": 4096}
        raw, error = engine.chat_json('JSON', 'x' * 100000, on_text_delta=lambda _: None)
        self.assertEqual(raw, '')
        self.assertIn('context_budget_exceeded', error)
        create.assert_not_called()
        client.with_options.assert_not_called()

    def test_byte_limit_is_bounded_and_not_retried(self):
        cases = [
            ([chunk('{"story_text":"' + '中' * 50000)], 'stream_output_limit'),
        ]
        for chunks, expected in cases:
            engine, stream, create, _ = stream_engine(chunks)
            raw, error = engine.chat_json('JSON', 'test', on_text_delta=lambda _: None)
            self.assertEqual(raw, '')
            self.assertIn(expected, error)
            self.assertEqual(create.call_count, 1)
            self.assertTrue(stream.closed)

    def test_many_content_reasoning_and_empty_chunks_complete_once(self):
        raw = json.dumps({'message': '长内容' * 1800}, ensure_ascii=False)
        chunks = [chunk(reasoning='推理') for _ in range(4100)]
        chunks += [chunk(reasoning=None) for _ in range(4100)]
        chunks += [chunk(char, reasoning=None) for char in raw]
        chunks.append(chunk(reason='stop'))
        engine, stream, create, _ = stream_engine(chunks)
        output = []
        result, error = engine.chat_json('JSON', 'workshop', on_text_delta=output.append, visible_fields=WORKSHOP_FIELDS)
        self.assertIsNone(error)
        self.assertEqual(result, raw)
        self.assertTrue(''.join(output).endswith('长内容' * 1800))
        self.assertNotIn('推理', ''.join(output))
        self.assertEqual(create.call_count, 1)
        self.assertTrue(stream.closed)

    def test_duration_limit_closes_stream_without_retry(self):
        engine, stream, create, _ = stream_engine([chunk()])
        with patch('core.ai_engine.time.monotonic', side_effect=[0, 601]):
            raw, error = engine.chat_json('JSON', 'test', on_text_delta=lambda _: None)
        self.assertEqual(raw, '')
        self.assertIn('stream_duration_limit', error)
        self.assertEqual(create.call_count, 1)
        self.assertTrue(stream.closed)

    def test_only_choice_zero_is_visible_and_tools_reject_even_with_stop(self):
        other = chunk('秘密分支', 'length').choices[0]
        other.index = 1
        public = chunk('{"story_text":"公开正文"}', 'stop')
        public.choices.append(other)
        engine, _, _, _ = stream_engine([public])
        output = []
        raw, error = engine.chat_json('JSON', 'test', on_text_delta=output.append)
        self.assertIsNone(error)
        self.assertEqual(''.join(output), '公开正文')
        engine, stream, create, _ = stream_engine([chunk('{"story_text":"正文"}', 'stop', tools=[{'secret': 'tool'}])])
        raw, error = engine.chat_json('JSON', 'test', on_text_delta=lambda _: None)
        self.assertEqual(raw, '')
        self.assertIn('stream_tools_unsupported', error)
        self.assertEqual(create.call_count, 1)
        self.assertTrue(stream.closed)


class StreamingTransportTests(unittest.TestCase):
    def test_complete_uses_original_payload_after_operation(self):
        def operation(emit):
            emit('中文\n第二行')
            return {"chat_messages": [{"role": "ai", "content": "正文"}], "state": {}}
        events = asyncio.run(collect(stream_response(operation, identity='story')))
        self.assertEqual([event for event, _ in events], ['start', 'delta', 'complete'])
        self.assertEqual(events[1][1], {'text': '中文\n第二行'})
        self.assertEqual(events[-1][1]['chat_messages'][0]['content'], '正文')

    def test_error_is_terminal_and_does_not_leak_raw_internal_exception(self):
        def operation(emit):
            emit('预览')
            raise RuntimeError('api-key-secret/raw-json')
        events = asyncio.run(collect(stream_response(operation)))
        self.assertEqual([event for event, _ in events], ['start', 'delta', 'error'])
        self.assertNotIn('secret', str(events[-1]))

    def test_same_workshop_busy_while_stream_executes_other_key_available(self):
        entered, release = threading.Event(), threading.Event()
        async def scenario():
            def operation(emit):
                entered.set()
                release.wait(2)
                return {"done": True}
            task = asyncio.create_task(collect(workshop_stream_response('lock-test', operation)))
            while not entered.is_set():
                await asyncio.sleep(.01)
            conflicting = await collect(workshop_stream_response('lock-test', operation))
            self.assertEqual(conflicting[-1][0], 'error')
            self.assertEqual(conflicting[-1][1]['code'], 409)
            with mutation_guard('workshop', 'other-test'):
                pass
            release.set()
            return await task
        events = asyncio.run(scenario())
        self.assertEqual(events[-1][0], 'complete')

    def test_disconnect_discards_preview_but_operation_finishes(self):
        entered, release, committed = threading.Event(), threading.Event(), threading.Event()
        def operation(emit):
            entered.set()
            release.wait(2)
            for _ in range(500):
                emit('不再需要的预览')
            committed.set()
            return {"saved": True}
        async def scenario():
            response = stream_response(operation)
            iterator = response.body_iterator
            await anext(iterator)
            await iterator.aclose()
            self.assertTrue(entered.wait(1))
            release.set()
        asyncio.run(scenario())
        self.assertTrue(committed.wait(1))

    def test_bounded_queue_slow_consumer_cannot_deadlock_worker(self):
        done = threading.Event()
        def operation(emit):
            for _ in range(1000):
                emit('预览')
            done.set()
            return {}
        async def scenario():
            response = stream_response(operation, queue_size=1)
            iterator = response.body_iterator
            await anext(iterator)
            await asyncio.sleep(.7)
            await iterator.aclose()
        asyncio.run(scenario())
        self.assertTrue(done.wait(1))


class _StreamingGame:
    def __init__(self, path):
        self.save_dir_path = str(path)
        self.plot_compass = ''
        self.history = {'chat_messages': [{'role': 'ai', 'content': '原正文'}], 'story_turns': []}
        self.state = {'before': True}
        self.action_suggestions = []
        self.is_game_over = False
        self.story_settings = {}
        self.calls = []
        self.capture_dispatches = 0

    def process_turn(self, action, *, on_text_delta=None):
        self.calls.append(('turn', action))
        on_text_delta('新正文')
        self.history['chat_messages'].extend([{'role': 'user', 'content': action}, {'role': 'ai', 'content': '新正文'}])
        self.state = {'after': True}
        return {}

    def reroll_turn(self, *, on_text_delta=None):
        self.calls.append(('reroll', ''))
        on_text_delta('重掷正文')
        self.history['chat_messages'] = [{'role': 'ai', 'content': '重掷正文'}]
        return {'chat_messages': self.history['chat_messages'], 'state': self.state, 'action_suggestions': []}

    def rollback(self):
        self.history['chat_messages'] = []
        return True

    def record_preference_interaction(self, *_args, **_kwargs):
        pass

    def capture_transaction_state(self):
        return copy.deepcopy((self.history, self.state, self.story_settings))

    def restore_transaction_state(self, state):
        self.history, self.state, self.story_settings = state

    def export_save_data(self):
        return {'history': self.history, 'state': self.state}

    def dispatch_committed_worldbook_captures(self):
        self.capture_dispatches += 1


class StreamingRouteTests(unittest.TestCase):
    def test_story_action_retry_reroll_payloads_and_save_before_complete(self):
        cases = [
            (game_routes.process_turn_stream, game_routes.ActionRequest(action='前进'), 'chat_messages'),
            (game_routes.retry_turn_stream, game_routes.ActionRequest(action='重试'), 'full_chat'),
            (game_routes.reroll_turn_stream, game_routes.EntityRuntimeRequest(), 'chat_messages'),
        ]
        with tempfile.TemporaryDirectory() as root:
            for route, payload, messages_key in cases:
                game = _StreamingGame(root)
                register_session('stream-story', game)
                try:
                    with patch('api.v1.game_routes.save_game_data') as save:
                        events = asyncio.run(collect(route('stream-story', payload)))
                    self.assertEqual(events[-1][0], 'complete')
                    self.assertIn(messages_key, events[-1][1])
                    self.assertEqual(len(game.calls), 1)
                    save.assert_called_once()
                    self.assertEqual(game.capture_dispatches, 1)
                finally:
                    unregister_session('stream-story')

    def test_failed_story_save_restores_original_turn_and_never_completes(self):
        with tempfile.TemporaryDirectory() as root:
            for route, payload in [
                (game_routes.process_turn_stream, game_routes.ActionRequest(action='行动')),
                (game_routes.retry_turn_stream, game_routes.ActionRequest(action='重试')),
                (game_routes.reroll_turn_stream, game_routes.EntityRuntimeRequest()),
            ]:
                game = _StreamingGame(root)
                before = game.capture_transaction_state()
                register_session('stream-story', game)
                try:
                    with patch('api.v1.game_routes.save_game_data', side_effect=OSError('disk full')):
                        events = asyncio.run(collect(route('stream-story', payload)))
                    self.assertEqual(events[-1][0], 'error')
                    self.assertEqual(game.capture_transaction_state(), before)
                    self.assertEqual(game.capture_dispatches, 0)
                finally:
                    unregister_session('stream-story')

    def test_story_lock_covers_persistence_not_only_provider(self):
        entered, release = threading.Event(), threading.Event()
        with tempfile.TemporaryDirectory() as root:
            game = _StreamingGame(root)
            register_session('stream-story', game)
            def save(*_args):
                entered.set()
                release.wait(2)
            async def scenario():
                task = asyncio.create_task(collect(game_routes.process_turn_stream('stream-story', game_routes.ActionRequest(action='行动'))))
                while not entered.is_set():
                    await asyncio.sleep(.01)
                with self.assertRaises(HTTPException) as raised:
                    game_routes.process_turn('stream-story', game_routes.ActionRequest(action='冲突'))
                self.assertEqual(raised.exception.status_code, 409)
                release.set()
                return await task
            try:
                with patch('api.v1.game_routes.save_game_data', side_effect=save):
                    events = asyncio.run(scenario())
                self.assertEqual(events[-1][0], 'complete')
            finally:
                release.set()
                unregister_session('stream-story')

    def test_all_workshop_chats_stream_and_disk_failure_keeps_live_object(self):
        with tempfile.TemporaryDirectory() as root:
            factories = [
                (worldbook_workshop_routes, WorldbookWorkshop('world-stream', Path(root)/'book.yml', {'name': '世界', 'entries': []}),
                 'WorldbookWorkshopAgent', worldbook_workshop_routes.WorkshopChatRequest(message='讨论', mode='expand'),
                 'core.model_connections.runtime.get_task_engine'),
                (preference_workshop_routes, PreferenceWorkshop('pref-stream', {'preferences': []}),
                 'PreferenceWorkshopAgent', preference_workshop_routes.ChatPayload(message='讨论'), '_engine'),
                (asset_workshop_routes, AssetWorkshop('asset-stream', 'characters', Path(root)/'character.yml', {'name': '角色', 'description': '原设定'}),
                 'AssetWorkshopAgent', asset_workshop_routes.ChatPayload(message='讨论'), '_engine'),
            ]
            for module, workshop, agent_name, payload, engine_name in factories:
                for fails in (False, True):
                    with self.subTest(module=module.__name__, fails=fails):
                        before = copy.deepcopy(workshop.__dict__)
                        def respond(candidate, *_args, **kwargs):
                            kwargs['on_text_delta']('正在讨论')
                            self.assertEqual(workshop.__dict__, before)
                            candidate.messages.append({'role': 'assistant', 'content': '最终讨论'})
                            candidate.dirty = True
                            return {'message': '最终讨论'}
                        target = engine_name if '.' in engine_name else f'{module.__name__}.{engine_name}'
                        agent = Mock()
                        agent.respond.side_effect = respond
                        with patch.object(module, '_get', return_value=workshop), patch(target, return_value=object()), \
                             patch.object(module, 'WORKSHOP_DIR', Path(root)), patch.object(module, agent_name, return_value=agent), \
                             patch.object(type(workshop), 'save_session', side_effect=OSError('disk full') if fails else None) as save:
                            events = asyncio.run(collect(module.chat_workshop_stream(workshop.id, payload)))
                        self.assertEqual(events[1], ('delta', {'text': '正在讨论'}))
                        self.assertEqual(events[-1][0], 'error' if fails else 'complete')
                        save.assert_called_once()
                        if fails:
                            self.assertEqual(workshop.__dict__, before)
                        else:
                            self.assertEqual(workshop.messages[-1]['content'], '最终讨论')


if __name__ == '__main__':
    unittest.main()
