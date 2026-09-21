import json
import tempfile
import unittest
from pathlib import Path

from core.prompt_studio import PromptOverrideStore, compose_prompt
from core.prompts import DEFAULT_PROMPTS, load_system_prompts
from core.settlement_prompt_sections import settlement_prompt_baselines, split_settlement_prompt


SETTLEMENT_SLICES = {
    "story.settlement.core",
    "story.state.guidance",
    "story.state.contract",
}


class SettlementPromptSectionTests(unittest.TestCase):
    def test_builtin_prompt_splits_and_reassembles_byte_for_byte(self):
        prompt = load_system_prompts()["settlement_prompt"]
        sections = split_settlement_prompt(prompt)
        self.assertTrue(sections.split)
        self.assertEqual(sections.compose(), prompt)
        self.assertIn("dynamic_bars", sections.state_guidance)
        for field in (
            "story_text", "new_buffs", "remove_buffs", "dynamic_bars",
            "status_updates", "npc_states", "status_deletions",
            "resolved_influences", "worldbook_capture_needed",
        ):
            self.assertIn(f'"{field}"', sections.state_contract)
        self.assertIn("current 和 max", sections.state_guidance)
        self.assertIn("current 与 change 只能二选一", sections.state_guidance)
        self.assertIn("恰好报告一次", sections.state_guidance)

    def test_emergency_fallback_prompt_uses_the_same_lossless_boundary_contract(self):
        prompt = DEFAULT_PROMPTS["settlement_prompt"]
        sections = split_settlement_prompt(prompt)
        self.assertTrue(sections.split)
        self.assertEqual(sections.compose(), prompt)

    def test_three_slices_render_exactly_like_the_legacy_prompt(self):
        prompt = load_system_prompts()["settlement_prompt"]
        expected = (prompt.replace("{style_info}", "文风")
                    .replace("{world_info}", "世界")
                    .replace("{character_info}", "角色"))
        with tempfile.TemporaryDirectory() as temporary:
            result = compose_prompt(
                "story.settlement",
                {"style_info": "文风", "world_info": "世界", "character_info": "角色"},
                include=SETTLEMENT_SLICES,
                store=PromptOverrideStore(Path(temporary) / "overrides.json"),
                baselines=settlement_prompt_baselines(prompt),
            )
        self.assertEqual(result.text, expected)
        self.assertEqual(
            [item["sliceId"] for item in result.manifest],
            ["story.settlement.core", "story.state.guidance", "story.state.contract"],
        )

    def test_unknown_layout_degrades_to_one_core_without_duplication(self):
        prompt = "自定义正文提示\n没有可识别的标题\n{style_info}"
        sections = split_settlement_prompt(prompt)
        self.assertFalse(sections.split)
        self.assertEqual(sections.compose(), prompt)
        self.assertEqual(sections.state_guidance, "")
        self.assertEqual(sections.state_contract, "")

    def test_legacy_full_core_override_is_atomically_split(self):
        prompt = load_system_prompts()["settlement_prompt"] + "\n自定义结尾"
        sections = split_settlement_prompt(prompt)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "overrides.json"
            path.write_text(json.dumps({"overrides": {
                "story.settlement.core": {"version": 4, "content": prompt},
            }}, ensure_ascii=False), encoding="utf-8")
            store = PromptOverrideStore(path)
            self.assertEqual(store.get("story.settlement.core")["content"], sections.core)
            self.assertEqual(store.get("story.state.guidance")["content"], sections.state_guidance)
            self.assertEqual(store.get("story.state.contract")["content"], sections.state_contract)
            migrated = json.loads(path.read_text(encoding="utf-8"))["overrides"]
            self.assertEqual(migrated["story.state.guidance"]["version"], 4)
            self.assertEqual(migrated["story.state.contract"]["migratedFrom"],
                             "story.settlement.core@legacy-full")

    def test_legacy_override_with_invalid_version_still_migrates_safely(self):
        prompt = load_system_prompts()["settlement_prompt"]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "overrides.json"
            path.write_text(json.dumps({"overrides": {
                "story.settlement.core": {"version": "损坏", "content": prompt},
            }}, ensure_ascii=False), encoding="utf-8")
            store = PromptOverrideStore(path)
            self.assertEqual(store.get("story.state.guidance")["version"], 1)


if __name__ == "__main__":
    unittest.main()
