import unittest
from unittest.mock import patch

from core.request_budget import budget_report
from tests.test_ai_engine import AIEngineTests, completion
from tests.test_streaming import stream_engine, chunk


class OutputRecoveryTests(unittest.TestCase):
    def test_connection_budget_overrides_task_default(self):
        report = budget_report('rules', 'request', 2600, {'output_reserve': 8192})
        self.assertEqual(report['outputReserve'], 8192)

    def test_nonstream_length_is_not_success_and_keeps_local_fragment(self):
        engine, create = AIEngineTests().make_engine([completion('{"story_text":"The door opened', 'length')])
        with patch('core.ai_engine.finish_llm_trace') as finish:
            raw, error = engine.chat_json('JSON', 'test')
        self.assertEqual(raw, '')
        self.assertIn('length', error)
        self.assertIn('The door opened', finish.call_args.kwargs['response'])
        self.assertEqual(create.call_count, 1)

    def test_stream_length_consumes_final_text_and_usage_without_settlement(self):
        usage = {'completion_tokens': 4096, 'completion_tokens_details': {'reasoning_tokens': 3746}}
        engine, stream, create, _ = stream_engine([
            chunk('{"story_text":"The door '), chunk('opened', 'length', usage=usage),
        ])
        visible = []
        with patch('core.ai_engine.finish_llm_trace') as finish:
            raw, error = engine.chat_json('JSON', 'test', on_text_delta=visible.append)
        self.assertEqual(raw, '')
        self.assertIn('length', error)
        self.assertEqual(''.join(visible), 'The door opened')
        self.assertEqual(finish.call_args.kwargs['metadata']['usage'], usage)
        self.assertTrue(stream.closed)
        self.assertEqual(create.call_count, 1)
