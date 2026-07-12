import unittest
from unittest.mock import patch

from core.future_candidates import candidate_probability, choose_candidate, normalize_candidates


class FutureCandidateTests(unittest.TestCase):
    def test_normalization_keeps_ineligible_candidate_out_of_random_pool(self):
        candidates = normalize_candidates([
            {"id": 1, "description": "取得胜利", "eligible": False, "weight": 999, "basis": "缺少必要物品"},
            {"id": 2, "description": "暂时撤退", "eligible": True, "weight": "25", "basis": ["仍有退路"]},
        ])

        self.assertEqual(candidates[0]["weight"], 0)
        self.assertEqual(candidates[0]["basis"], ["缺少必要物品"])
        self.assertEqual(choose_candidate(candidates)["id"], 2)

    def test_old_candidate_protocol_remains_compatible(self):
        candidates = normalize_candidates([{"id": 1, "description": "旧存档候选", "weight": 60}])

        self.assertTrue(candidates[0]["eligible"])
        self.assertEqual(candidates[0]["basis"], [])

    def test_relative_weights_are_normalized_only_for_debug_probability(self):
        candidates = normalize_candidates([
            {"id": 1, "description": "甲", "weight": 30},
            {"id": 2, "description": "乙", "weight": 10},
        ])

        self.assertAlmostEqual(candidate_probability(candidates[0], candidates), 0.75)
        with patch("core.future_candidates.random.choices", return_value=[candidates[1]]) as mocked:
            chosen = choose_candidate(candidates)
        self.assertEqual(chosen["id"], 2)
        self.assertEqual(mocked.call_args.kwargs["weights"], [30.0, 10.0])

    def test_empty_or_zero_weight_payload_gets_safe_fallback(self):
        candidates = normalize_candidates([{"description": "无权重候选", "weight": 0}])

        self.assertEqual(len(candidates), 1)
        self.assertGreater(candidates[0]["weight"], 0)
        self.assertIn("当前事实", candidates[0]["description"])

    def test_reroll_avoids_previous_candidate_when_possible(self):
        candidates = normalize_candidates([
            {"id": 1, "description": "旧结果", "weight": 100},
            {"id": 2, "description": "新结果", "weight": 1},
        ])

        self.assertEqual(choose_candidate(candidates, exclude_description="旧结果")["id"], 2)


if __name__ == "__main__":
    unittest.main()
