import tempfile
import unittest

from core.game_session import GameSession
from core.story_settings import DEFAULT_STORY_SETTINGS, normalize_story_settings
from core.story_length import story_length_instruction


class StorySettingsTests(unittest.TestCase):
    def test_soft_range_normalization_and_save_roundtrip(self):
        self.assertEqual(normalize_story_settings()['minimumStoryLength'], 0)
        for value, expected in [(None, 0), ('', 0), (-2, 0), (350, 350), (900, 800)]:
            settings = normalize_story_settings({'targetStoryLength': 800, 'minimumStoryLength': value})
            self.assertEqual(settings['minimumStoryLength'], expected)
        session = GameSession(None)
        session.story_settings = normalize_story_settings({'targetStoryLength': 1200, 'minimumStoryLength': 600})
        restored = GameSession(None)
        restored.load_save_data(session.export_save_data())
        self.assertEqual(restored.story_settings, session.story_settings)
        text = story_length_instruction(1200, 600)
        self.assertIn('600–1200', text)
        self.assertIn('软建议', text)
        self.assertIn('只约束 story_text', text)

    def test_notification_preferences_survive_save_without_changing_review(self):
        defaults = normalize_story_settings()
        self.assertTrue(defaults['worldbookNotices'])
        self.assertFalse(defaults['worldbookDetailedNotices'])
        self.assertFalse(defaults['worldbookNoticeContent'])
        session = GameSession(None)
        session.story_settings = normalize_story_settings({'worldbookNotices': False,
            'worldbookDetailedNotices': True, 'worldbookNoticeContent': True, 'worldbookCaptureReview': True})
        restored = GameSession(None)
        restored.load_save_data(session.export_save_data())
        self.assertEqual(restored.story_settings, session.story_settings)
        self.assertTrue(restored.story_settings['worldbookCaptureEnabled'])
        self.assertTrue(restored.story_settings['worldbookCaptureReview'])

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
            session.action_suggestions = ["调查钟楼", "询问守卫"]

            world_info, _ = session.build_active_world_info("调查钟楼")
            saved = session.export_save_data()

            self.assertNotIn("不要立刻揭晓凶手", world_info)
            self.assertEqual(saved["world_premise"], "蒸汽都市中存在隐秘魔法")
            self.assertEqual(saved["plot_compass"], "近期调查失踪案，不要立刻揭晓凶手")
            self.assertFalse(saved["story_settings"]["entitiesEnabled"])
            self.assertEqual(saved["action_suggestions"], ["调查钟楼", "询问守卫"])

            restored = GameSession(None, save_dir_path=temp_dir)
            restored.load_save_data(saved)
            self.assertEqual(restored.world_premise, session.world_premise)
            self.assertEqual(restored.plot_compass, session.plot_compass)
            self.assertFalse(restored.story_settings["entitiesEnabled"])
            self.assertEqual(restored.action_suggestions, ["调查钟楼", "询问守卫"])

    def test_disabled_suggestions_do_not_restore_stale_save_values(self):
        session = GameSession(None)
        session.load_save_data({
            "story_settings": {"aiSuggestions": False},
            "action_suggestions": ["不应恢复"],
            "history": {"chat_messages": [{"role": "ai", "content": "正文", "suggestions": ["也不应恢复"]}], "context_history": []},
        })
        self.assertEqual(session.action_suggestions, [])

    def test_preference_emphasis_defaults_and_roundtrip(self):
        self.assertEqual(normalize_story_settings()['preferenceEmphasis'], 'balanced')
        self.assertEqual(normalize_story_settings({'preferenceEmphasis': 'invalid'})['preferenceEmphasis'], 'balanced')
        session = GameSession(None)
        session.story_settings = normalize_story_settings({'preferenceEmphasis': 'light'})
        restored = GameSession(None)
        restored.load_save_data(session.export_save_data())
        self.assertEqual(restored.story_settings['preferenceEmphasis'], 'light')

    def test_legacy_description_migrates_to_world_premise(self):
        session = GameSession(None)
        session.load_save_data({"description": "旧版宇宙简述"})
        self.assertEqual(session.world_premise, "旧版宇宙简述")
        self.assertEqual(session.plot_compass, "")

    def test_story_length_is_numeric_clamped_and_restored(self):
        self.assertEqual(normalize_story_settings({"targetStoryLength": "900"})["targetStoryLength"], 900)
        self.assertEqual(normalize_story_settings({"targetStoryLength": 50})["targetStoryLength"], 200)
        self.assertEqual(normalize_story_settings({"targetStoryLength": 99999})["targetStoryLength"], 3000)
        session = GameSession(None)
        session.load_save_data({"word_limit": 760})
        self.assertEqual(session.story_settings["targetStoryLength"], 760)
        self.assertEqual(session.word_limit, 760)
        self.assertIn("约 760 个中文字符", story_length_instruction(760))

    def test_experience_preset_is_finite_and_legacy_saves_get_default(self):
        self.assertEqual(
            normalize_story_settings({"storyExperiencePreset": "engine_only"})["storyExperiencePreset"],
            "engine_only",
        )
        self.assertEqual(
            normalize_story_settings({"storyExperiencePreset": "unknown"})["storyExperiencePreset"],
            "aliveworld_default",
        )
        self.assertEqual(normalize_story_settings({})["storyExperiencePreset"], "aliveworld_default")


if __name__ == "__main__":
    unittest.main()
