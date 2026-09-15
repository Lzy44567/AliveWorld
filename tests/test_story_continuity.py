import unittest

from core.story_continuity import continuity_instruction


class StoryContinuityContractTests(unittest.TestCase):
    def test_contract_protects_information_channels_and_local_observations(self):
        prompt = continuity_instruction()
        self.assertIn("局部、单次的未发现", prompt)
        self.assertIn("不能自动推出", prompt)
        self.assertIn("外部介入", prompt)
        self.assertIn("知情者、发生时间", prompt)
        self.assertIn("信息或行动通道", prompt)
        self.assertIn("不得只为绕过", prompt)
        self.assertIn("不能替代因果通道", prompt)
        for scenario_word in ("警察", "保安", "对讲机", "自动报警"):
            self.assertNotIn(scenario_word, prompt)

    def test_contract_scopes_npc_radar_to_current_scene(self):
        prompt = continuity_instruction()
        self.assertIn("npc_states", prompt)
        self.assertIn("当前场景", prompt)
        self.assertIn("status_deletions", prompt)


if __name__ == "__main__":
    unittest.main()
