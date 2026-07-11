import tempfile
import unittest

from core.game_session import GameSession
from core.story_settings import DEFAULT_STORY_SETTINGS, normalize_story_settings


class StorySettingsTests(unittest.TestCase):
    def test_partial_and_unknown_settings_are_normalized(self):
        settings = normalize_story_settings({"showDice": False, "unknown": True})
        self.assertFalse(settings["showDice"])
        self.assertTrue(settings["entitiesEnabled"])
        self.assertNotIn("unknown", settings)
        self.assertEqual(set(settings), set(DEFAULT_STORY_SETTINGS))

    def test_world_premise_and_plot_compass_are_persisted_separately(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session = GameSession(None, "测试故事", temp_dir, {"entitiesEnabled": False})
            session.world_premise = "蒸汽都市中存在隐秘魔法"
            session.plot_compass = "近期调查失踪案，不要立刻揭晓凶手"

            world_info, _ = session.build_active_world_info("调查钟楼")
            saved = session.export_save_data()

            self.assertIn("主线剧情导向", world_info)
            self.assertIn("不要立刻揭晓凶手", world_info)
            self.assertEqual(saved["world_premise"], "蒸汽都市中存在隐秘魔法")
            self.assertEqual(saved["plot_compass"], "近期调查失踪案，不要立刻揭晓凶手")
            self.assertFalse(saved["story_settings"]["entitiesEnabled"])

            restored = GameSession(None, save_dir_path=temp_dir)
            restored.load_save_data(saved)
            self.assertEqual(restored.world_premise, session.world_premise)
            self.assertEqual(restored.plot_compass, session.plot_compass)
            self.assertFalse(restored.story_settings["entitiesEnabled"])

    def test_legacy_description_migrates_to_world_premise(self):
        session = GameSession(None)
        session.load_save_data({"description": "旧版宇宙简述"})
        self.assertEqual(session.world_premise, "旧版宇宙简述")
        self.assertEqual(session.plot_compass, "")


if __name__ == "__main__":
    unittest.main()
