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


if __name__ == "__main__":
    unittest.main()
