import unittest

from core.story_continuity import continuity_instruction


class StoryContinuityContractTests(unittest.TestCase):
    def test_contract_protects_information_channels_and_local_observations(self):
        prompt = continuity_instruction()
        self.assertIn("某处没找到", prompt)
        self.assertIn("不能自动推出", prompt)
        self.assertIn("外部介入", prompt)
        self.assertIn("信号被完全屏蔽", prompt)
        self.assertIn("对讲机不能工作", prompt)
        self.assertIn("不得只为绕过", prompt)
        self.assertIn("不能替代报警", prompt)
        self.assertIn("所有未来候选", prompt)

    def test_contract_scopes_npc_radar_to_current_scene(self):
        prompt = continuity_instruction()
        self.assertIn("npc_states", prompt)
        self.assertIn("当前场景", prompt)
        self.assertIn("status_deletions", prompt)


if __name__ == "__main__":
    unittest.main()
