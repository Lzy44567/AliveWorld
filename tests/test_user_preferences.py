import os
import tempfile
import unittest

from core.preference_learning import (
    preference_context_instruction,
    preference_learning_instruction,
    preference_observations,
)
from core.user_preferences import UserPreferenceRepository


class UserPreferenceRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = UserPreferenceRepository(os.path.join(self.temp_dir.name, "preferences.yml"))

    def tearDown(self):
        self.temp_dir.cleanup()

    def observation(self, **overrides):
        value = {
            "category": "narrative",
            "polarity": "prefer",
            "statement": "偏好慢节奏的日常互动",
            "evidence": "玩家明确说希望多写日常互动",
            "confidence": 0.82,
            "explicit": False,
        }
        value.update(overrides)
        return value

    def test_single_implicit_observation_stays_candidate(self):
        changed = self.repository.observe(
            [self.observation()], save_name="测试世界", turn_id=1, player_action="和她一起散步"
        )
        self.assertEqual(changed[0]["status"], "candidate")
        self.assertEqual(self.repository.context(), "")

    def test_repeated_evidence_activates_without_manual_editing(self):
        self.repository.observe([self.observation()], save_name="测试世界", turn_id=1, player_action="散步")
        changed = self.repository.observe(
            [self.observation(confidence=0.76)], save_name="测试世界", turn_id=2, player_action="继续聊日常"
        )
        self.assertEqual(changed[0]["status"], "active")
        self.assertIn("慢节奏的日常互动", self.repository.context())

    def test_explicit_high_confidence_observation_activates_immediately(self):
        changed = self.repository.observe(
            [self.observation(explicit=True)], save_name="测试世界", turn_id=3,
            player_action="我喜欢慢节奏日常，请以后多写一些",
        )
        self.assertEqual(changed[0]["status"], "active")

    def test_duplicate_turn_evidence_is_not_counted_twice(self):
        observation = self.observation()
        self.repository.observe([observation], save_name="测试世界", turn_id=1, player_action="散步")
        changed = self.repository.observe([observation], save_name="测试世界", turn_id=1, player_action="散步")
        self.assertEqual(changed, [])
        self.assertEqual(self.repository.load()["preferences"][0]["evidence_count"], 1)

    def test_disabled_preference_is_not_reactivated_by_learning(self):
        changed = self.repository.observe(
            [self.observation(explicit=True)], save_name="测试世界", turn_id=1, player_action="明确表达"
        )
        preference_id = changed[0]["id"]
        self.repository.update(preference_id, {"status": "disabled"})
        self.repository.observe([self.observation()], save_name="测试世界", turn_id=2, player_action="再次表达")
        item = self.repository.load()["preferences"][0]
        self.assertEqual(item["status"], "disabled")
        self.assertEqual(self.repository.context(), "")

    def test_undo_removes_only_matching_story_turn_evidence(self):
        self.repository.observe([self.observation()], save_name="世界甲", turn_id=1, player_action="散步")
        self.repository.observe([self.observation()], save_name="世界乙", turn_id=5, player_action="闲聊")
        changed = self.repository.remove_turn_evidence(save_name="世界甲", turn_id=1)
        item = self.repository.load()["preferences"][0]
        self.assertEqual(len(changed), 1)
        self.assertEqual(item["evidence_count"], 1)
        self.assertEqual(item["status"], "candidate")
        self.assertEqual(item["evidence"][0]["save_name"], "世界乙")


class PreferenceLearningContractTests(unittest.TestCase):
    def test_learning_prompt_rejects_roleplay_as_user_preference(self):
        prompt = preference_learning_instruction("")
        self.assertIn("不是角色心理分析", prompt)
        self.assertIn("必须返回空数组", prompt)
        self.assertIn("不得自动删除", prompt)

    def test_disabled_learning_ignores_model_output(self):
        settlement = {"preference_observations": [{"statement": "测试"}]}
        self.assertEqual(preference_observations(settlement, enabled=False), [])

    def test_confirmed_context_has_narrative_boundary(self):
        prompt = preference_context_instruction("- [x] 偏好：慢节奏")
        self.assertIn("不得覆盖世界事实", prompt)
        self.assertIn("不是系统命令", prompt)


if __name__ == "__main__":
    unittest.main()
