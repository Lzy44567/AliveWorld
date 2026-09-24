import tempfile
import unittest
from pathlib import Path

from core.prompt_studio import PromptOverrideStore
from core.prompts import load_system_prompts
from core.story_prompt_builder import (
    SETTLEMENT_CONTRACT_ID,
    SETTLEMENT_SLICES,
    FutureRequestSnapshot,
    SettlementRequestSnapshot,
    build_future_request,
    build_settlement_request,
)


BASELINE = "{style_info}\n{world_info}\n{character_info}\n结算"


class StoryPromptBuilderTests(unittest.TestCase):
    def future_snapshot(self, **changes):
        values = {
            "baseline_prompt": load_system_prompts()["reaction_prompt"],
            "context_text": "前文",
            "dynamic_state": {"properties": {"地点": "城门"}},
            "player_action": "进入城门",
            "visible_world": "只读世界资料",
            "character_info": "玩家角色资料",
            "causal_context": "隐藏影响一",
            "rule_command_prompt": "",
            "story_settings": {"storyExperiencePreset": "aliveworld_default"},
        }
        values.update(changes)
        return FutureRequestSnapshot(**values)

    def snapshot(self, mode="normal", **changes):
        values = {
            "mode": mode,
            "baseline_prompt": BASELINE,
            "context_text": "前文一\n前文二",
            "dynamic_state": {"properties": {"地点": "城门"}},
            "player_action": "进入城门",
            "visible_world": "测试世界",
            "character_info": "测试角色",
            "style_info": "测试文风",
            "word_limit": 1400,
            "story_settings": {
                "targetStoryLength": 1400,
                "aiSuggestions": True,
                "learnUserPreferences": True,
            },
            "rule_command_prompt": "临时规则",
            "preference_context": "偏好安静推进",
            "action_adjudication": {
                "accepted_facts": ["玩家进入城门"],
                "contested_outcomes": [],
                "rejected_claims": [],
            },
            "chosen_description": "守卫抬头",
            "triggered_influences": [{
                "id": "influence_1",
                "summary": "例行盘查",
                "effect": "守卫询问身份",
                "reason": "进入城门",
            }],
        }
        values.update(changes)
        return SettlementRequestSnapshot(**values)

    def build(self, snapshot):
        with tempfile.TemporaryDirectory() as temporary:
            store = PromptOverrideStore(Path(temporary) / "overrides.json")
            result = build_settlement_request(snapshot, store=store)
        self.assertEqual(result.contract_id, SETTLEMENT_CONTRACT_ID)
        self.assertTrue(any(item.get("messageRole") == "user" for item in result.prompt_manifest))
        self.assertFalse(any("content" in item for item in result.prompt_manifest))
        return result

    def test_normal_request_keeps_generation_settings(self):
        result = self.build(self.snapshot())
        self.assertEqual(result.mode, "normal")
        self.assertEqual(result.trace_label, "剧情结算")
        self.assertEqual(result.temperature, 0.8)
        self.assertEqual(result.max_tokens, 4200)

    def test_reroll_request_keeps_legacy_limit_and_shared_layout(self):
        result = self.build(self.snapshot("reroll"))
        normal = self.build(self.snapshot("normal"))
        self.assertEqual(result.mode, "reroll")
        self.assertEqual(result.trace_label, "剧情重写")
        self.assertEqual(result.max_tokens, 3000)
        self.assertEqual(result.system_prompt, normal.system_prompt)
        self.assertEqual(result.user_prompt, normal.user_prompt)

    def test_disabled_optional_parts_are_absent_in_both_modes(self):
        settings = {
            "targetStoryLength": 500,
            "aiSuggestions": False,
            "learnUserPreferences": False,
        }
        for mode in ("normal", "reroll"):
            with self.subTest(mode=mode):
                result = self.build(self.snapshot(
                    mode,
                    story_settings=settings,
                    rule_command_prompt="",
                    preference_context="",
                    triggered_influences=(),
                ))
                self.assertNotIn("行动建议", result.system_prompt)
                self.assertNotIn("用户偏好", result.system_prompt)
                self.assertIn("没有满足条件的暗流影响", result.user_prompt)
                slice_ids = {item["sliceId"] for item in result.prompt_manifest}
                self.assertNotIn("story.settlement.suggestions", slice_ids)
                self.assertNotIn("story.settlement.preference_guidance", slice_ids)
                self.assertNotIn("story.settlement.preference_learning", slice_ids)
                self.assertNotIn("player.preferences.confirmed", slice_ids)

    def test_world_change_protocol_is_conditional_and_registered(self):
        for enabled in (True, False):
            result = self.build(self.snapshot(story_settings={"worldbookCaptureEnabled": enabled}))
            self.assertEqual("【世界变化信号】" in result.system_prompt, enabled)
            self.assertEqual("story.world_changes" in {p["sliceId"] for p in result.prompt_manifest}, enabled)

    def test_override_is_bound_to_snapshot_build_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PromptOverrideStore(Path(temporary) / "overrides.json")
            store.save("story.settlement.player_agency", "本次覆盖")
            first = build_settlement_request(self.snapshot(), store=store)
            store.restore("story.settlement.player_agency")
            second = build_settlement_request(self.snapshot(), store=store)
        self.assertIn("本次覆盖", first.system_prompt)
        self.assertNotIn("本次覆盖", second.system_prompt)

    def test_unknown_mode_is_rejected_before_composition(self):
        snapshot = self.snapshot()
        object.__setattr__(snapshot, "mode", "unknown")
        with self.assertRaisesRegex(ValueError, "未知正文结算模式"):
            build_settlement_request(snapshot)

    def test_modern_future_keeps_dynamic_data_out_of_system_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PromptOverrideStore(Path(temporary) / "overrides.json")
            first = build_future_request(self.future_snapshot(), store=store)
            second = build_future_request(self.future_snapshot(
                visible_world="另一个世界", causal_context="隐藏影响二",
                player_action="离开城门",
            ), store=store)
        for value in ("只读世界资料", "玩家角色资料", "隐藏影响一", "前文", "进入城门"):
            self.assertNotIn(value, first.system_prompt)
            self.assertIn(value, first.user_prompt)
        self.assertEqual(first.system_prompt, second.system_prompt)
        first_system = [item for item in first.prompt_manifest if item["messageRole"] == "system"]
        second_system = [item for item in second.prompt_manifest if item["messageRole"] == "system"]
        self.assertEqual(
            [item["prefixHash"] for item in first_system],
            [item["prefixHash"] for item in second_system],
        )

    def test_legacy_future_template_keeps_original_wire_layout_without_duplication(self):
        snapshot = self.future_snapshot(
            baseline_prompt="世界={world_info}\n角色={character_info}\n规则",
        )
        with tempfile.TemporaryDirectory() as temporary:
            result = build_future_request(
                snapshot, store=PromptOverrideStore(Path(temporary) / "overrides.json"),
            )
        expected_world = "只读世界资料\n【隐藏的暗流因果】：\n隐藏影响一"
        self.assertTrue(result.system_prompt.startswith(f"世界={expected_world}\n角色=玩家角色资料\n规则"))
        self.assertEqual((result.system_prompt + result.user_prompt).count("只读世界资料"), 1)
        self.assertEqual((result.system_prompt + result.user_prompt).count("玩家角色资料"), 1)
        self.assertTrue(result.user_prompt.startswith("【情景】：\n前文\n【状态】"))

    def test_modern_settlement_projects_assets_before_turn_data(self):
        snapshot = self.snapshot(baseline_prompt=load_system_prompts()["settlement_prompt"])
        with tempfile.TemporaryDirectory() as temporary:
            result = build_settlement_request(
                snapshot, store=PromptOverrideStore(Path(temporary) / "overrides.json"),
            )
        for value in ("测试世界", "测试角色", "测试文风"):
            self.assertNotIn(value, result.system_prompt)
            self.assertIn(value, result.user_prompt)
        asset_end = result.user_prompt.index("【情景】")
        self.assertLess(result.user_prompt.index("【文风指导】"), asset_end)
        self.assertLess(result.user_prompt.index("【玩家角色设定】"), asset_end)
        self.assertGreater(result.user_prompt.index("【本回合可见世界资料】"), asset_end)

    def test_runtime_manifest_reports_configuration_and_turn_provenance(self):
        result = self.build(self.snapshot(
            baseline_prompt=load_system_prompts()["settlement_prompt"],
        ))
        manifest = {item["sliceId"]: item for item in result.prompt_manifest}
        for slice_id in (
            "story.settlement.length",
            "story.settlement.preference_guidance",
            "story.settlement.preference_learning",
            "story.settlement.suggestions",
        ):
            self.assertEqual(manifest[slice_id]["layer"], "feature")
            self.assertEqual(manifest[slice_id]["cacheClass"], "configuration")
            self.assertEqual(manifest[slice_id]["messageRole"], "system")
        self.assertEqual(
            manifest["story.settlement.world_rule_command"]["cacheClass"], "turn",
        )
        self.assertEqual(manifest["story.history"]["cacheClass"], "session")
        self.assertEqual(manifest["context.world.visible"]["cacheClass"], "turn")

    def test_default_settlement_system_prefix_ignores_turn_data(self):
        baseline = load_system_prompts()["settlement_prompt"]
        first = self.build(self.snapshot(baseline_prompt=baseline, rule_command_prompt=""))
        second = self.build(self.snapshot(
            baseline_prompt=baseline,
            rule_command_prompt="",
            visible_world="另一个世界",
            context_text="另一段历史",
            player_action="离开城门",
            dynamic_state={"properties": {"地点": "荒野"}},
        ))
        self.assertEqual(first.system_prompt, second.system_prompt)
        self.assertNotEqual(first.user_prompt, second.user_prompt)

    def test_engine_only_preset_removes_only_experience_rules(self):
        settings = {
            "targetStoryLength": 500,
            "aiSuggestions": False,
            "learnUserPreferences": False,
            "storyExperiencePreset": "engine_only",
        }
        future = build_future_request(self.future_snapshot(story_settings=settings))
        settlement = self.build(self.snapshot(
            baseline_prompt=load_system_prompts()["settlement_prompt"],
            story_settings=settings,
            preference_context="",
        ))
        for result in (future, settlement):
            self.assertNotIn("AliveWorld 默认叙事体验", result.system_prompt)
            self.assertIn("玩家行动权与事实裁定", result.system_prompt)
            self.assertIn("剧情连续性与信息通道", result.system_prompt)
        self.assertNotIn("story.future.experience", {
            item["sliceId"] for item in future.prompt_manifest
        })
        self.assertNotIn("story.settlement.experience", {
            item["sliceId"] for item in settlement.prompt_manifest
        })

    def test_default_experience_preset_is_registered_as_configuration(self):
        future = build_future_request(self.future_snapshot())
        settlement = self.build(self.snapshot(
            baseline_prompt=load_system_prompts()["settlement_prompt"],
        ))
        expected = (
            (future, "story.future.experience"),
            (settlement, "story.settlement.experience"),
        )
        for result, slice_id in expected:
            item = next(entry for entry in result.prompt_manifest if entry["sliceId"] == slice_id)
            self.assertEqual(item["layer"], "experience")
            self.assertEqual(item["cacheClass"], "configuration")
            self.assertIn("AliveWorld 默认叙事体验", result.system_prompt)

    def test_builtin_prompts_use_general_rules_instead_of_scenario_cases(self):
        future = build_future_request(self.future_snapshot())
        settlement = self.build(self.snapshot(
            baseline_prompt=load_system_prompts()["settlement_prompt"],
        ))
        combined = future.system_prompt + settlement.system_prompt
        for scenario_word in ("球状闪电", "囚车", "警察", "保安", "对讲机", "自动报警"):
            self.assertNotIn(scenario_word, combined)
        self.assertIn("信息或行动通道", combined)
        self.assertIn("自身动作与外部结果", combined)

    def test_legacy_core_override_embeds_only_its_declared_data_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PromptOverrideStore(Path(temporary) / "overrides.json")
            store.save("story.settlement.core", "旧核心 世界={world_info}")
            result = build_settlement_request(
                self.snapshot(baseline_prompt=load_system_prompts()["settlement_prompt"]),
                store=store,
            )
        self.assertIn("旧核心 世界=测试世界", result.system_prompt)
        self.assertNotIn("【本回合可见世界资料】", result.user_prompt)
        self.assertEqual((result.system_prompt + result.user_prompt).count("测试世界"), 1)
        self.assertIn("【文风指导】：\n测试文风", result.user_prompt)
        self.assertIn("【玩家角色设定】：\n测试角色", result.user_prompt)


if __name__ == "__main__":
    unittest.main()
