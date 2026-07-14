import unittest

from core.chat_messages import ensure_message_ids


class ChatMessageTests(unittest.TestCase):
    def test_adds_and_preserves_unique_ids(self):
        messages = [{"role": "ai", "content": "a"}, {"id": "keep", "role": "user", "content": "b"}]
        ensure_message_ids(messages)
        first_id = messages[0]["id"]
        ensure_message_ids(messages)
        self.assertEqual(messages[0]["id"], first_id)
        self.assertEqual(messages[1]["id"], "keep")

    def test_duplicate_id_is_replaced(self):
        messages = [{"id": "same"}, {"id": "same"}]
        ensure_message_ids(messages)
        self.assertEqual(messages[0]["id"], "same")
        self.assertNotEqual(messages[1]["id"], "same")


if __name__ == "__main__":
    unittest.main()
