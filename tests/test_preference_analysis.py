import os
import tempfile
import unittest

import json

from core.preference_analysis import PreferenceAnalysisService, update_probability
from core.game_session import GameSession
from core.user_preferences import UserPreferenceRepository
from api.v1.game_routes import _interaction_context


class PreferenceBayesianTests(unittest.TestCase):
    def test_python_owns_ordinal_probability_update(self):
        self.assertAlmostEqual(update_probability(0.2, "support", "strong"), 0.5)
        self.assertAlmostEqual(update_probability(0.5, "against", "moderate"), 1 / 3)
        self.assertEqual(update_probability(0.4, "neutral", "strong"), 0.4)

    def test_unknown_assessment_is_neutral(self):
        self.assertAlmostEqual(update_probability(0.35, "support", "invented"), 0.35)


class PreferenceAnalysisRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = UserPreferenceRepository(os.path.join(self.temp_dir.name, "preferences.yml"))

    def tearDown(self):
        self.temp_dir.cleanup()

    def add_evidence(self, save_name, turn_id, summary):
        return self.repository.record_evidence([{
            "signal_type": "choice", "summary": summary, "context": "测试情境",
            "diagnosticity": "moderate", "sensitive": False,
        }], save_name=save_name, turn_id=turn_id)[0]

    def test_analysis_keeps_competing_hypotheses_and_coverage_gap(self):
        evidence = self.add_evidence("故事甲", 1, "玩家在人群中施法并观察反应")
        payload = {
            "hypotheses": [
                {
                    "statement": "偏好让旁观者对角色能力表现出惊讶", "category": "relationship",
                    "polarity": "prefer", "sensitive": False,
                    "assessments": [{"evidence_id": evidence["id"], "direction": "support", "strength": "moderate", "reason": "关注反馈"}],
                },
                {
                    "statement": "偏好公开展示角色力量", "category": "story",
                    "polarity": "prefer", "sensitive": False,
                    "assessments": [{"evidence_id": evidence["id"], "direction": "support", "strength": "weak", "reason": "也可能只是战术"}],
                },
            ],
            "coverage_note": "单次行为不能区分表演欲、战术和好奇。",
            "missing_possibilities": ["可能只是测试法术效果"],
        }
        changed = self.repository.apply_analysis(payload, [evidence])
        profile = self.repository.load()
        self.assertEqual(len(changed), 2)
        self.assertTrue(all(item["status"] == "candidate" for item in changed))
        self.assertIn("不能区分", profile["analysis"]["coverage_note"])
        self.assertEqual(profile["analysis"]["missing_possibilities"], ["可能只是测试法术效果"])

    def test_inferred_preference_requires_high_posterior_and_two_stories(self):
        first = self.add_evidence("故事甲", 1, "重复观察群众反应一")
        second = self.add_evidence("故事乙", 2, "重复观察群众反应二")
        payload = {
            "hypotheses": [{
                "statement": "偏好旁观者惊讶的反馈", "category": "relationship", "polarity": "prefer",
                "assessments": [
                    {"evidence_id": first["id"], "direction": "support", "strength": "strong"},
                    {"evidence_id": second["id"], "direction": "support", "strength": "strong"},
                ],
            }],
            "coverage_note": "仍非穷尽。", "missing_possibilities": [],
        }
        item = self.repository.apply_analysis(payload, [first, second])[0]
        self.assertEqual(item["status"], "active")
        self.assertEqual(item["posterior"], 0.8)

    def test_undo_removes_behavior_and_recomputes_posterior(self):
        first = self.add_evidence("故事甲", 1, "证据一")
        second = self.add_evidence("故事乙", 2, "证据二")
        payload = {
            "hypotheses": [{
                "statement": "偏好某种反馈", "category": "relationship", "polarity": "prefer",
                "assessments": [
                    {"evidence_id": first["id"], "direction": "support", "strength": "strong"},
                    {"evidence_id": second["id"], "direction": "support", "strength": "strong"},
                ],
            }],
        }
        self.repository.apply_analysis(payload, [first, second])
        self.repository.remove_turn_evidence(save_name="故事乙", turn_id=2)
        item = self.repository.load()["preferences"][0]
        self.assertEqual(item["status"], "candidate")
        self.assertEqual(item["posterior"], 0.5)
        self.assertEqual(item["evidence_count"], 1)

    def test_manual_reanalysis_can_reuse_old_evidence_for_missed_cause(self):
        evidence = self.add_evidence("故事甲", 1, "玩家反复查看旁观者反应")
        self.repository.apply_analysis({"hypotheses": [], "coverage_note": "暂未找到原因"}, [evidence])

        class FakeEngine:
            def chat_json(self, *_args, **_kwargs):
                return json.dumps({
                    "hypotheses": [{
                        "statement": "偏好旁观者惊讶的反馈", "category": "relationship", "polarity": "prefer",
                        "assessments": [{"evidence_id": evidence["id"], "direction": "support", "strength": "weak"}],
                    }],
                    "coverage_note": "仍可能存在其他原因", "missing_possibilities": ["战术确认"],
                }, ensure_ascii=False), None

        result = PreferenceAnalysisService(FakeEngine()).analyze_now(
            self.repository, include_sensitive=False, force=True,
        )
        self.assertEqual(len(result["changed"]), 1)
        self.assertEqual(result["changed"][0]["status"], "candidate")

    def test_interaction_evidence_is_weak_and_survives_story_rollback(self):
        story_evidence = self.add_evidence("故事甲", 3, "正文记录的故事选择")
        interaction = self.repository.record_interaction(
            signal_type="reroll",
            summary="玩家要求重新抽取未来结果",
            context="原因未知，也可能只是希望获胜",
            save_name="故事甲",
            related_turn_id=3,
        )
        self.repository.remove_turn_evidence(save_name="故事甲", turn_id=3)
        profile = self.repository.load()
        ids = {item["id"] for item in profile["evidence"]}
        self.assertNotIn(story_evidence["id"], ids)
        self.assertIn(interaction["id"], ids)
        self.assertEqual(interaction["diagnosticity"], "weak")
        self.assertEqual(interaction["source"], "interaction")
        self.assertFalse(interaction["reversible"])


class PreferenceInteractionPolicyTests(unittest.TestCase):
    def session(self, enabled=True):
        session = GameSession.__new__(GameSession)
        session.story_settings = {
            "learnUserPreferences": enabled,
            "deepPreferenceAnalysis": True,
            "analyzeSensitivePreferences": False,
        }
        session.save_name = "测试故事"

        class Repository:
            def __init__(self):
                self.calls = []

            def record_interaction(self, **kwargs):
                self.calls.append(kwargs)
                return {"id": "evidence_ui"}

        class Analysis:
            def __init__(self):
                self.calls = []

            def schedule(self, *args, **kwargs):
                self.calls.append((args, kwargs))

        session.user_preferences = Repository()
        session.preference_analysis = Analysis()
        return session

    def test_game_session_respects_learning_switch_for_ui_events(self):
        session = self.session(enabled=False)
        self.assertIsNone(session.record_preference_interaction("undo", "玩家撤回"))
        self.assertEqual(session.user_preferences.calls, [])
        self.assertEqual(session.preference_analysis.calls, [])

    def test_game_session_records_and_schedules_ui_event(self):
        session = self.session(enabled=True)
        result = session.record_preference_interaction(
            "reroll", "玩家重掷", "原因未知", related_turn_id=8
        )
        self.assertEqual(result["id"], "evidence_ui")
        self.assertEqual(session.user_preferences.calls[0]["related_turn_id"], 8)
        self.assertEqual(len(session.preference_analysis.calls), 1)

    def test_ui_event_context_does_not_copy_story_or_player_text(self):
        context = _interaction_context({
            "turn_id": 8,
            "player": "这里是敏感玩家行动",
            "story": "这里是敏感故事正文",
        })
        self.assertIn("关联故事回合：8", context)
        self.assertNotIn("敏感玩家行动", context)
        self.assertNotIn("敏感故事正文", context)


if __name__ == "__main__":
    unittest.main()
