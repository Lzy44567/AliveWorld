import unittest

from core.player_agency import adjudication_context, normalize_action_adjudication, player_agency_instruction


class PlayerAgencyContractTests(unittest.TestCase):
    def test_contract_protects_corrections_and_separates_external_outcome(self):
        prompt = player_agency_instruction()
        self.assertIn("括号内纠错", prompt)
        self.assertIn("成功发射", prompt)
        self.assertIn("囚车是否摧毁", prompt)
        self.assertIn("不得把整句降级", prompt)
        self.assertIn("不得擅自改成", prompt)

    def test_adjudication_is_normalized_and_rendered_for_settlement(self):
        raw = {
            "accepted_facts": ["玩家成功发射球状闪电", "玩家成功发射球状闪电", ""],
            "contested_outcomes": [{"claim": "囚车被摧毁", "reason": "影响外部世界"}],
            "rejected_claims": [{"claim": "NPC立刻投降", "basis": "NPC意愿不由玩家决定"}],
            "ignored": "not trusted",
        }
        normalized = normalize_action_adjudication(raw)
        self.assertEqual(normalized["accepted_facts"], ["玩家成功发射球状闪电"])
        self.assertNotIn("ignored", normalized)
        context = adjudication_context(normalized)
        self.assertIn("正文不得否认", context)
        self.assertIn("囚车被摧毁", context)
        self.assertIn("NPC立刻投降", context)

    def test_missing_adjudication_has_safe_empty_shape(self):
        self.assertEqual(
            normalize_action_adjudication(None),
            {"accepted_facts": [], "contested_outcomes": [], "rejected_claims": []},
        )

    def test_settlement_rules_do_not_request_a_second_adjudication(self):
        prompt = player_agency_instruction(require_output=False)
        self.assertIn("不得擅自改成", prompt)
        self.assertNotIn('"action_adjudication"', prompt)


if __name__ == "__main__":
    unittest.main()
