import json
import unittest
from dataclasses import replace
from unittest.mock import patch

import httpx
from openai import AsyncOpenAI
from core.character_chat.models import CharacterSessionError
from core.character_chat.transport import CharacterTransport
from core.prompt_studio import ModelRequestPlan


class CharacterTransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = {'model': 'synthetic-model', 'api_key': 'SYNTHETIC_SECRET', 'base_url': 'http://synthetic.invalid/v1'}
        self.plan = ModelRequestPlan('PRIVATE_PROFILE_SYNTHETIC', 'PRIVATE_INPUT_SYNTHETIC',
            [{'sliceId': 'character.context', 'contentHash': 'safehash'}], 0.8, None, 'character.reply', 'json', 'character.reply.v1')
        self.report = {'outputReserve': 4096, 'fits': True}
        self.calls = []
        self.response_body = {'id': 'synthetic', 'choices': [{'index': 0, 'finish_reason': 'stop',
            'message': {'role': 'assistant', 'content': '{"reply":"PRIVATE_REPLY_SYNTHETIC","ledger_ops":[]}'}}]}

    def handler(self, request):
        self.calls.append(json.loads(request.content))
        return httpx.Response(200, json=self.response_body)

    def factory(self, **kwargs):
        self.assertEqual(0, kwargs['max_retries'])
        return AsyncOpenAI(**kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(self.handler)))

    async def run_transport(self, delivery='non_stream'):
        with patch('core.character_chat.transport.AsyncOpenAI', side_effect=self.factory), \
                patch('core.character_chat.transport.begin_llm_trace', return_value='safe-trace') as begin, \
                patch('core.character_chat.transport.finish_llm_trace') as finish:
            raw = await CharacterTransport().generate(self.config, self.plan, self.report, delivery, lambda _: None)
            return raw, begin, finish

    async def test_real_sdk_one_call_no_trace_body_and_no_usage_extension(self):
        raw, begin, finish = await self.run_transport()
        self.assertIn('PRIVATE_REPLY_SYNTHETIC', raw)
        self.assertEqual(1, len(self.calls))
        self.assertEqual({'type': 'json_object'}, self.calls[0]['response_format'])
        self.assertNotIn('stream_options', self.calls[0])
        traces = str(begin.call_args_list) + str(finish.call_args_list)
        for secret in ('PRIVATE_PROFILE_SYNTHETIC', 'PRIVATE_INPUT_SYNTHETIC', 'PRIVATE_REPLY_SYNTHETIC', 'SYNTHETIC_SECRET'):
            self.assertNotIn(secret, traces)

    async def test_default_logger_and_diagnostics_receive_no_private_content(self):
        with patch('core.character_chat.transport.AsyncOpenAI', side_effect=self.factory), \
                patch('core.llm_trace.log') as log, patch('core.llm_trace.record_request') as diagnostics:
            await CharacterTransport().generate(self.config, self.plan, self.report, 'non_stream', lambda _: None)
        captured = str(log.mock_calls) + str(diagnostics.mock_calls)
        self.assertIn('character.reply', captured)
        self.assertIn('private content omitted', captured)
        for private in ('PRIVATE_PROFILE_SYNTHETIC', 'PRIVATE_INPUT_SYNTHETIC', 'PRIVATE_REPLY_SYNTHETIC', 'SYNTHETIC_SECRET'):
            self.assertNotIn(private, captured)

    async def test_contact_plan_uses_one_nonstream_call_and_own_private_trace(self):
        plan = replace(self.plan, contract_id='character.contact_plan.v1',
                       context_contract_id='character.contact_context.v1')
        with patch('core.character_chat.transport.AsyncOpenAI', side_effect=self.factory), \
                patch('core.character_chat.transport.begin_llm_trace', return_value='contact-trace') as begin, \
                patch('core.character_chat.transport.finish_llm_trace') as finish:
            await CharacterTransport().generate_contact(self.config, plan, self.report)
        self.assertEqual(1, len(self.calls))
        self.assertNotIn('stream', self.calls[0])
        self.assertEqual('character.contact', begin.call_args.args[0])
        self.assertEqual('character.contact', finish.call_args.args[0])
        self.assertNotIn('PRIVATE_PROFILE_SYNTHETIC', str(begin.call_args))

    async def test_contact_plan_cannot_call_provider_with_reply_contract(self):
        with self.assertRaises(CharacterSessionError):
            await CharacterTransport().generate_contact(self.config, self.plan, self.report)
        self.assertEqual([], self.calls)

    async def test_http_failure_zero_sdk_retries_safe_error(self):
        def handler(request):
            self.calls.append(json.loads(request.content))
            return httpx.Response(500, json={'error': {'message': 'PRIVATE_UPSTREAM_ERROR SYNTHETIC_SECRET'}})
        self.handler = handler
        with self.assertRaises(CharacterSessionError) as caught:
            await self.run_transport()
        self.assertEqual('PROVIDER_FAILED', caught.exception.code)
        self.assertEqual(1, len(self.calls))
        self.assertNotIn('PRIVATE', str(caught.exception))

    async def test_nonstream_multiple_choices_tools_and_truncation_rejected(self):
        variations = [
            {'choices': self.response_body['choices'] * 2},
            {'choices': [{'index': 0, 'finish_reason': 'length', 'message': {'content': 'partial', 'role': 'assistant'}}]},
            {'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'content': '{}', 'role': 'assistant',
                'tool_calls': [{'id': 'id', 'type': 'function', 'function': {'name': 'forbidden', 'arguments': '{}'}}]}}]},
        ]
        for body in variations:
            self.response_body = body
            with self.assertRaises(CharacterSessionError):
                await self.run_transport()
        self.assertEqual(3, len(self.calls))

    async def test_real_sdk_sse_escaped_preview_and_stop_same_chunk(self):
        raw = json.dumps({'reply': '逐字中文 😀', 'ledger_ops': []}, ensure_ascii=True)
        chunks = []
        for i, part in enumerate([raw[:13], raw[13:23], raw[23:]]):
            chunks.append('data: ' + json.dumps({'id': 's', 'object': 'chat.completion.chunk',
                'choices': [{'index': 0, 'delta': {'content': part}, 'finish_reason': 'stop' if i == 2 else None}]}) + '\n\n')
        chunks.append('data: [DONE]\n\n')
        def handler(request):
            self.calls.append(json.loads(request.content))
            return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=''.join(chunks))
        self.handler = handler
        preview = []
        with patch('core.character_chat.transport.AsyncOpenAI', side_effect=self.factory), \
                patch('core.character_chat.transport.begin_llm_trace', return_value='safe'), \
                patch('core.character_chat.transport.finish_llm_trace'):
            actual = await CharacterTransport().generate(self.config, self.plan, self.report, 'stream', preview.append)
        self.assertEqual(raw, actual)
        self.assertEqual('逐字中文 😀', ''.join(preview))
        self.assertEqual(1, len(self.calls))
        self.assertTrue(self.calls[0]['stream'])

    async def test_real_sdk_stream_invalid_finish_and_tools_single_call(self):
        for choice in ({'index': 0, 'delta': {'content': '{"reply":"partial'}, 'finish_reason': 'length'},
                       {'index': 0, 'delta': {'tool_calls': [{'index': 0, 'id': 'id', 'type': 'function', 'function': {'name': 'x'}}]}, 'finish_reason': None}):
            def handler(request):
                self.calls.append(json.loads(request.content))
                raw = 'data: ' + json.dumps({'id': 's', 'object': 'chat.completion.chunk', 'choices': [choice]}) + '\n\ndata: [DONE]\n\n'
                return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=raw)
            self.handler = handler
            with self.assertRaises(CharacterSessionError):
                await self.run_transport('stream')
        self.assertEqual(2, len(self.calls))

    async def test_v2_sdk_stream_accepts_annotations_only_with_frozen_protocol(self):
        raw = json.dumps({'reply': '回复🙂', 'ledger_ops': [], 'memory_annotations': []}, ensure_ascii=True)
        def handler(request):
            self.calls.append(json.loads(request.content))
            event = {'id': 's', 'object': 'chat.completion.chunk', 'choices': [{'index': 0,
                'delta': {'content': raw}, 'finish_reason': 'stop'}]}
            return httpx.Response(200, headers={'content-type': 'text/event-stream'},
                                  content='data: ' + json.dumps(event) + '\n\ndata: [DONE]\n\n')
        self.handler = handler
        self.plan = replace(self.plan, contract_id='character.reply.v2')
        actual, _, _ = await self.run_transport('stream')
        self.assertEqual(raw, actual); self.assertEqual(1, len(self.calls))
        self.plan = replace(self.plan, contract_id='character.reply.v1')
        with self.assertRaises(CharacterSessionError): await self.run_transport('stream')
        self.plan = replace(self.plan, contract_id='character.reply.v99')
        with self.assertRaises(CharacterSessionError) as exc: await self.run_transport('stream')
        self.assertEqual('REPLY_CONTRACT_UNSUPPORTED', exc.exception.code); self.assertEqual(2, len(self.calls))

    async def test_v3_one_sdk_call_separate_realtime_bubbles_and_private_paths(self):
        from core.character_chat.protocol import V3
        from tests.test_character_multibubble_protocol import result, visible
        value = result('第一条🙂', '第二条')
        # Preview never exposes a private same-named nested field. Final contract
        # validation (not transport) will reject the deliberately bad ledger.
        value['ledger_ops'] = [{'source': {'text': 'PRIVATE'}, 'content': 'SECRET'}]
        raw = json.dumps(value, ensure_ascii=True)
        chunks = []
        for index, char in enumerate(raw):
            event = {'id': 's', 'object': 'chat.completion.chunk', 'choices': [{'index': 0,
                'delta': {'content': char}, 'finish_reason': 'stop' if index == len(raw) - 1 else None}]}
            chunks.append('data: ' + json.dumps(event) + '\n\n')
        def handler(request):
            self.calls.append(json.loads(request.content))
            return httpx.Response(200, headers={'content-type': 'text/event-stream'},
                                  content=''.join(chunks) + 'data: [DONE]\n\n')
        self.handler = handler
        self.plan = replace(self.plan, contract_id=V3)
        events = []
        with patch('core.character_chat.transport.AsyncOpenAI', side_effect=self.factory), \
                patch('core.character_chat.transport.begin_llm_trace', return_value='safe'), \
                patch('core.character_chat.transport.finish_llm_trace') as finish:
            actual = await CharacterTransport().generate(self.config, self.plan, self.report, 'stream', events.append)
        self.assertEqual(raw, actual)
        self.assertEqual({0: '第一条🙂', 1: '第二条'}, visible(events))
        self.assertEqual(1, len(self.calls))
        self.assertEqual(2, sum(e['kind'] == 'preview_start' for e in events))
        self.assertNotIn('SECRET', str(finish.mock_calls))

    async def test_v3_nonstream_still_one_call_no_preview_or_implicit_retry(self):
        from core.character_chat.protocol import V3
        from tests.test_character_multibubble_protocol import result
        self.plan = replace(self.plan, contract_id=V3)
        raw = json.dumps(result('一', '二', '三'))
        self.response_body['choices'][0]['message']['content'] = raw
        actual, _, _ = await self.run_transport()
        self.assertEqual(raw, actual)
        self.assertEqual(1, len(self.calls))
        self.assertNotIn('stream', self.calls[0])
