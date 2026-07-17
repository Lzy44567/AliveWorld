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

    def test_json_blank_response_retries_once(self):
        engine, create = self.make_engine([
            completion("   "),
            completion('{"ok": true}', response_id="response-retry"),
        ])

        raw, error = engine.chat_json("输出 JSON", "执行测试", trace_label="测试")

        self.assertIsNone(error)
        self.assertEqual('{"ok": true}', raw)
        self.assertEqual(2, create.call_count)
        retry_messages = create.call_args_list[1].kwargs["messages"]
        self.assertIn("禁止只输出空白字符", retry_messages[-1]["content"])

    def test_content_filter_is_not_retried(self):
        engine, create = self.make_engine([completion("", "content_filter")])

        raw, error = engine.chat_json("输出 JSON", "执行测试", trace_label="测试")

        self.assertEqual("", raw)
        self.assertIn("content_filter", error)
        self.assertEqual(1, create.call_count)


if __name__ == "__main__":
    unittest.main()
