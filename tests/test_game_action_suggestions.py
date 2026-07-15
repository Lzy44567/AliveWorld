import tempfile
import unittest

from core.game_session import GameSession


class FakeResolver:
    def __init__(self, suggestions):
        self.suggestions = suggestions

    def resolve(self, _session, _action):
        return {
            "reactions": [{"id": 1, "description": "广场保持平静", "eligible": True, "weight": 1, "basis": []}],
            "chosen_reaction": {"id": 1, "description": "广场保持平静", "eligible": True, "weight": 1, "basis": []},
            "triggered_influences": [],
            "settlement": {
                "story_text": "玩家来到广场。",
                "resolved_influences": [],
                "action_suggestions": self.suggestions,
                "worldbook_capture_needed": False,
            },
        }


class GameActionSuggestionTests(unittest.TestCase):
    def test_turn_persists_suggestions_on_ai_message_and_save(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session = GameSession(None, "测试", temp_dir)
            session.start_new_game("", "开场")
            session.resolver = FakeResolver(["观察广场", "询问路人", "观察广场"])
            session.process_turn("前往广场")

            self.assertEqual(session.action_suggestions, ["观察广场", "询问路人"])
            ai_message = next(message for message in reversed(session.history["chat_messages"]) if message["role"] == "ai")
            self.assertEqual(ai_message["suggestions"], session.action_suggestions)
            self.assertEqual(session.export_save_data()["action_suggestions"], session.action_suggestions)

    def test_turn_discards_suggestions_when_story_setting_is_off(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session = GameSession(None, "测试", temp_dir, {"aiSuggestions": False})
            session.start_new_game("", "开场")
            session.resolver = FakeResolver(["不应显示"])
            session.process_turn("等待")
            self.assertEqual(session.action_suggestions, [])


if __name__ == "__main__":
    unittest.main()
