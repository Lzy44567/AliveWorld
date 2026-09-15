import json
import tempfile
import unittest
from pathlib import Path

from core.action_suggestions import action_suggestion_instruction
from core.player_agency import adjudication_context, normalize_action_adjudication
from core.preference_learning import preference_context_instruction, preference_learning_instruction
from core.prompt_studio import PromptOverrideStore, compose_prompt
from core.settlement_prompt_sections import settlement_prompt_baselines
from core.story_length import story_length_instruction
from core.story_prompt_builder import (
    SETTLEMENT_CONTRACT_ID,
    SETTLEMENT_SLICES,
    SettlementRequestSnapshot,
    build_settlement_request,
)


BASELINE = "{style_info}\n{world_info}\n{character_info}\n结算"


def legacy_request(snapshot, store):
    preference = preference_context_instruction(snapshot.preference_context)
    suggestion = action_suggestion_instruction(snapshot.story_settings.get("aiSuggestions", True))
    parts = {
        "rule": ("story.settlement.world_rule_command", snapshot.rule_command_prompt, "runtime"),
        "length": (
            "story.settlement.length",
            story_length_instruction(snapshot.story_settings.get("targetStoryLength")),
            "runtime",
        ),
        "suggestions": (
            "story.settlement.suggestions",
            ("【玩家行动建议要求】\n" + suggestion) if suggestion else "",
            "runtime",
        ),
        "preference": ("story.settlement.preference_context", preference, "runtime"),
        "learning": (
            "story.settlement.preference_learning",
            preference_learning_instruction(snapshot.preference_context)
            if snapshot.story_settings.get("learnUserPreferences", True)
            else "",
            "runtime",
        ),
    }
    order = (
        ("rule", "length", "preference", "learning", "suggestions")
        if snapshot.mode == "normal"
        else ("rule", "length", "suggestions", "preference", "learning")
    )
    system = compose_prompt(
        "story.settlement",
        {
            "world_info": snapshot.visible_world,
            "character_info": snapshot.character_info,
            "style_info": snapshot.style_info,
            "word_limit": snapshot.word_limit,
        },
        include=SETTLEMENT_SLICES,
        runtime_parts=[parts[key] for key in order],
        baselines=settlement_prompt_baselines(snapshot.baseline_prompt),
        store=store,
    ).text
    influence = "\n".join(
        f"- [{item['id']}] {item['summary']}；必须体现的后果：{item['effect']}；依据：{item['reason']}"
        for item in snapshot.triggered_influences
    ) or "（本回合没有满足条件的暗流影响）"
    user = (
        f"【情景】：\n{snapshot.context_text}"
        f"\n【状态】：{json.dumps(snapshot.dynamic_state, ensure_ascii=False)}"
        f"\n【行动】：{snapshot.player_action}"
        f"\n{adjudication_context(normalize_action_adjudication(snapshot.action_adjudication))}"
        f"\n【裁定变数】：{snapshot.chosen_description}"
        f"\n【本回合必须兑现的暗流影响】：\n{influence}"
    )
    return system, user


class StoryPromptBuilderTests(unittest.TestCase):
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

    def assert_legacy_equivalent(self, snapshot):
        with tempfile.TemporaryDirectory() as temporary:
            store = PromptOverrideStore(Path(temporary) / "overrides.json")
            expected_system, expected_user = legacy_request(snapshot, store)
            result = build_settlement_request(snapshot, store=store)
        self.assertEqual(result.system_prompt, expected_system)
        self.assertEqual(result.user_prompt, expected_user)
        self.assertEqual(result.contract_id, SETTLEMENT_CONTRACT_ID)
        self.assertTrue(any(item.get("messageRole") == "user" for item in result.prompt_manifest))
        self.assertFalse(any("content" in item for item in result.prompt_manifest))
        return result

    def test_normal_request_is_byte_equivalent_and_keeps_generation_settings(self):
        result = self.assert_legacy_equivalent(self.snapshot())
        self.assertEqual(result.mode, "normal")
        self.assertEqual(result.trace_label, "剧情结算")
        self.assertEqual(result.temperature, 0.8)
        self.assertEqual(result.max_tokens, 4200)

    def test_reroll_request_is_byte_equivalent_and_keeps_legacy_limit(self):
        result = self.assert_legacy_equivalent(self.snapshot("reroll"))
        self.assertEqual(result.mode, "reroll")
        self.assertEqual(result.trace_label, "剧情重写")
        self.assertEqual(result.max_tokens, 3000)

    def test_disabled_optional_parts_are_absent_in_both_modes(self):
        settings = {
            "targetStoryLength": 500,
            "aiSuggestions": False,
            "learnUserPreferences": False,
        }
        for mode in ("normal", "reroll"):
            with self.subTest(mode=mode):
                result = self.assert_legacy_equivalent(self.snapshot(
                    mode,
                    story_settings=settings,
                    rule_command_prompt="",
                    preference_context="",
                    triggered_influences=(),
                ))
                self.assertNotIn("行动建议", result.system_prompt)
                self.assertNotIn("用户偏好", result.system_prompt)
                self.assertIn("没有满足条件的暗流影响", result.user_prompt)

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


if __name__ == "__main__":
    unittest.main()
