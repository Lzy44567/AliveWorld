import unittest

from core.action_suggestions import action_suggestion_instruction, normalize_action_suggestions


class ActionSuggestionTests(unittest.TestCase):
    def test_normalize_deduplicates_flattens_and_caps(self):
        value = [" 观察周围\n寻找线索 ", "观察周围 寻找线索", 123, "询问守卫", "检查背包", "暂时离开", "多余选项"]
        self.assertEqual(
            normalize_action_suggestions(value),
            ["观察周围 寻找线索", "询问守卫", "检查背包", "暂时离开"],
        )

    def test_disabled_setting_discards_model_output(self):
        self.assertEqual(normalize_action_suggestions(["偷看隐藏陷阱"], enabled=False), [])
        self.assertIn("空数组", action_suggestion_instruction(False))

    def test_prompt_explicitly_forbids_hidden_information(self):
        prompt = action_suggestion_instruction(True)
        self.assertIn("未触发陷阱", prompt)
        self.assertIn("未被选中的未来候选", prompt)


if __name__ == "__main__":
    unittest.main()
