import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.ai_engine import AIEngine


def completion(content, finish_reason="stop", response_id="response-test"):
    return SimpleNamespace(
        id=response_id,
        choices=[SimpleNamespace(
            finish_reason=finish_reason,
            message=SimpleNamespace(content=content),
        )],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


class AIEngineTests(unittest.TestCase):
    def make_engine(self, responses):
        create = Mock(side_effect=responses)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch("core.ai_engine.OpenAI", return_value=client):
            engine = AIEngine({"api_key": "test", "base_url": "http://localhost", "model": "test-model"})
        return engine, create

    def test_json_blank_response_does_not_override_retry_setting(self):
        engine, create = self.make_engine([
            completion("   "),
            completion('{"ok": true}', response_id="response-retry"),
        ])

        raw, error = engine.chat_json("输出 JSON", "执行测试", trace_label="测试")

        self.assertIn('empty_response', error)
        self.assertEqual('', raw)
        self.assertEqual(1, create.call_count)

    def test_content_filter_is_not_retried(self):
        engine, create = self.make_engine([completion("", "content_filter")])

        raw, error = engine.chat_json("输出 JSON", "执行测试", trace_label="测试")

        self.assertEqual("", raw)
        self.assertIn("content_filter", error)
        self.assertEqual(1, create.call_count)

    def test_output_limit_is_not_retried_with_the_same_budget(self):
        engine, create = self.make_engine([completion('', 'length')])
        raw, error = engine.chat_json('输出 JSON', '执行测试')
        self.assertEqual('', raw)
        self.assertIn('length:', error)
        self.assertEqual(1, create.call_count)


if __name__ == "__main__":
    unittest.main()
