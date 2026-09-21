import unittest

from core.settlement_contract import SettlementContractError, validate_settlement
from core.state_manager import StateManager


class SettlementContractTests(unittest.TestCase):
    def test_defaults_optional_fields_and_filters_untrusted_influence_reports(self):
        result = validate_settlement(
            {
                "story_text": "正文继续。",
                "resolved_influences": [
                    {"id": "unknown", "result": "越权"},
                    {"id": "required", "result": "已经兑现"},
                    {"id": "required", "result": "重复提交"},
                ],
            },
            current_state={},
            triggered_ids={"required"},
        )

        self.assertEqual(result["resolved_influences"], [{"id": "required", "result": "已经兑现"}])
        for field in ("new_buffs", "dynamic_bars", "status_updates", "npc_states"):
            self.assertEqual(result[field], {})
        for field in ("remove_buffs", "status_deletions"):
            self.assertEqual(result[field], [])

    def test_missing_required_influence_is_contract_error(self):
        with self.assertRaisesRegex(SettlementContractError, "缺少必须兑现"):
            validate_settlement(
                {"story_text": "正文继续。", "resolved_influences": []},
                current_state={},
                triggered_ids={"required"},
            )

    def test_existing_bar_rejects_current_and_change_together(self):
        with self.assertRaisesRegex(SettlementContractError, "current 或 change 之一"):
            validate_settlement(
                {
                    "story_text": "状态变化。",
                    "dynamic_bars": {"生命": {"current": 8, "change": -2}},
                },
                current_state={"bars": {"生命": {"current": 10, "max": 10}}},
            )

    def test_new_bar_requires_absolute_current_and_max(self):
        with self.assertRaisesRegex(SettlementContractError, "新进度条不能使用 change"):
            validate_settlement(
                {"story_text": "状态变化。", "dynamic_bars": {"生命": {"change": -2}}},
                current_state={"bars": {}},
            )
        with self.assertRaisesRegex(SettlementContractError, "必须同时提供 current 和 max"):
            validate_settlement(
                {"story_text": "状态变化。", "dynamic_bars": {"生命": {"current": 8}}},
                current_state={"bars": {}},
            )

    def test_ambiguous_name_deletion_is_rejected(self):
        state = {
            "properties": {"中毒": "严重"},
            "bars": {},
            "buffs": {"中毒": {"duration": 2}},
            "npcs": {},
        }
        with self.assertRaisesRegex(SettlementContractError, "名称删除存在歧义"):
            validate_settlement(
                {"story_text": "状态变化。", "status_deletions": ["中毒"]},
                current_state=state,
            )

    def test_state_plan_failure_never_partially_mutates_live_state(self):
        manager = StateManager()
        manager.state["bars"]["生命"] = {"current": 10, "max": 10, "change": 0, "color": "red"}
        before = manager.get_dynamic_state().copy()

        with self.assertRaises(TypeError):
            manager.apply_updates({"new_buffs": {"异常": {"生命_per_turn": "不是数值"}}})

        self.assertEqual(manager.state["bars"]["生命"]["current"], 10)
        self.assertNotIn("异常", manager.state["buffs"])
        self.assertEqual(manager.get_dynamic_state()["properties"], before["properties"])

    def test_state_plan_is_invisible_until_explicit_commit(self):
        manager = StateManager()
        manager.state["bars"]["生命"] = {"current": 10, "max": 10, "change": 0, "color": "red"}
        plan = manager.plan_updates({
            "new_buffs": {"灼烧": {"生命_per_turn": -2, "duration": 2}},
            "dynamic_bars": {"生命": {"change": -1}},
        })

        self.assertEqual(manager.state["bars"]["生命"]["current"], 10)
        self.assertEqual(plan.state["bars"]["生命"]["current"], 7)
        manager.commit(plan)
        self.assertEqual(manager.state["bars"]["生命"]["current"], 7)

    def test_buff_runtime_fields_must_match_state_engine_types(self):
        with self.assertRaisesRegex(SettlementContractError, "duration"):
            validate_settlement({
                "story_text": "继续。",
                "new_buffs": {"中毒": {"duration": 1.5, "生命值_per_turn": -2}},
            })
        with self.assertRaisesRegex(SettlementContractError, "生命值_per_turn"):
            validate_settlement({
                "story_text": "继续。",
                "new_buffs": {"中毒": {"duration": 2, "生命值_per_turn": "-2"}},
            })

    def test_worldbook_capture_flag_must_be_boolean_when_present(self):
        with self.assertRaisesRegex(SettlementContractError, "worldbook_capture_needed"):
            validate_settlement({"story_text": "继续。", "worldbook_capture_needed": "yes"})


if __name__ == "__main__":
    unittest.main()
