import unittest

from core.model_response import failure_message, format_story_text


class ModelResponseTests(unittest.TestCase):
    def test_formats_long_single_block(self):
        self.assertIn("\n\n", format_story_text("第一句很长。" * 50))

    def test_preserves_existing_paragraphs(self):
        value = "第一段。\n\n第二段。"
        self.assertEqual(value, format_story_text(value))

    def test_connection_message_is_explicit(self):
        message = failure_message("Connection error")
        self.assertIn("网络", message)
        self.assertIn("未保存", message)

    def test_provider_failure_messages_are_distinct(self):
        self.assertIn("过滤", failure_message("content_filter: blocked"))
        self.assertIn("长度限制", failure_message("length: empty"))
        self.assertIn("推理资源不足", failure_message("insufficient_system_resource"))
        self.assertIn("空白内容", failure_message("empty_response: stop"))


if __name__ == "__main__":
    unittest.main()
