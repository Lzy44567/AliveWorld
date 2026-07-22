import os
import tempfile
import unittest

import json

from core.preference_analysis import PreferenceAnalysisService, update_probability
from core.user_preferences import UserPreferenceRepository


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


if __name__ == "__main__":
    unittest.main()
