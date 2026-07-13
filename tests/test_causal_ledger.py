import unittest

from core.causal_ledger import CausalLedger


def influence(summary, action="keep", mode="never", influence_type="persistent"):
    return {
        "source_links": [{"entity": "疫病术士", "life_link_strength": 0.9, "on_source_death": action}],
        "type": influence_type,
        "summary": summary,
        "condition": "玩家接近",
        "effect": "发生后果",
        "consume_policy": {"mode": mode, "max_triggers": 1 if mode == "after_n" else None},
    }


class CausalLedgerTests(unittest.TestCase):
    def test_cancelled_influence_can_be_restored(self):
        ledger = CausalLedger([{"id": "restore_me", "summary": "可恢复", "status": "cancelled"}])
        self.assertEqual(ledger.restore("restore_me").status, "active")

    def test_only_inactive_influence_can_be_permanently_deleted(self):
        ledger = CausalLedger([{"id": "active", "summary": "生效"}, {"id": "old", "summary": "旧账", "status": "cancelled"}])
        self.assertIsNone(ledger.purge("active"))
        self.assertEqual(ledger.purge("old").id, "old")
        self.assertIsNone(ledger.by_id("old"))

    def test_turn_age_condition_check_and_one_shot_consumption(self):
        ledger = CausalLedger()
        item = ledger.add(influence("弩箭陷阱", mode="on_success", influence_type="one_shot"), current_tick=3)
        ledger.advance_turn()

        triggered = ledger.evaluate_checks([
            {"id": item.id, "condition_met": True, "reason": "玩家踩中机关"},
            {"id": "不存在", "condition_met": True, "reason": "伪造"},
        ])
        resolved = ledger.resolve([{"id": item.id, "result": "弩箭射出"}])

        self.assertEqual(item.age_ticks, 1)
        self.assertEqual(item.attempt_count, 1)
        self.assertEqual(len(triggered), 1)
        self.assertEqual(resolved, [item])
        self.assertEqual(item.trigger_count, 1)
        self.assertEqual(item.status, "consumed")
        self.assertEqual(item.last_check_reason, "玩家踩中机关")
        self.assertEqual(item.trigger_history[0]["result"], "弩箭射出")
        self.assertEqual(item.trigger_history[0]["tick"], ledger.turn_count)

    def test_persistent_influence_can_trigger_repeatedly(self):
        ledger = CausalLedger()
        item = ledger.add(influence("长期通缉", mode="never"))
        for _ in range(2):
            ledger.evaluate_checks([{"id": item.id, "condition_met": True, "reason": "进入辖区"}])
            ledger.resolve([{"id": item.id, "result": "遭到盘查"}])

        self.assertEqual(item.trigger_count, 2)
        self.assertEqual(item.status, "active")

    def test_source_death_removes_mercenaries_releases_plague_and_keeps_social_effect(self):
        ledger = CausalLedger()
        mercenaries = ledger.add(influence("雇佣队失去雇主", action="remove"))
        plague = ledger.add(influence("尸体爆发瘟疫", action="release", mode="on_success", influence_type="one_shot"))
        wanted = ledger.add(influence("既有通缉令", action="keep"))

        result = ledger.handle_source_death("疫病术士")
        triggered = ledger.evaluate_checks([])

        self.assertEqual(mercenaries.status, "cancelled")
        self.assertIn(mercenaries, result["removed"])
        self.assertTrue(plague.force_next_turn)
        self.assertEqual(triggered[0]["id"], plague.id)
        self.assertTrue(plague.source_links[0]["source_dead"])
        self.assertEqual(wanted.status, "active")
        self.assertTrue(wanted.source_links[0]["source_dead"])

    def test_entity_reference_is_projection_of_central_record(self):
        ledger = CausalLedger()
        item = ledger.add(influence("环境中的瘟疫", action="release"))
        refs = ledger.refs_for_entity("疫病术士")

        self.assertEqual(refs[0]["id"], item.id)
        self.assertEqual(refs[0]["life_link_strength"], 0.9)
        self.assertEqual(refs[0]["on_source_death"], "release")
        self.assertNotIn("condition", refs[0])

    def test_player_turn_counter_advances_without_overseer_and_persists_creation_tick(self):
        ledger = CausalLedger(turn_count=7)
        ledger.advance_turn()
        item = ledger.add(influence("第八回合创建"), current_tick=ledger.turn_count)

        self.assertEqual(ledger.turn_count, 8)
        self.assertEqual(item.created_tick, 8)

    def test_context_prioritizes_forced_then_newer_influences(self):
        ledger = CausalLedger()
        old = ledger.add({**influence("旧影响"), "created_tick": 1})
        newest = ledger.add({**influence("新影响"), "created_tick": 9})
        forced = ledger.add({**influence("死亡释放"), "created_tick": 2, "force_next_turn": True})

        context = ledger.context(item_limit=2)

        self.assertIn(forced.id, context)
        self.assertIn(newest.id, context)
        self.assertNotIn(old.id, context)


if __name__ == "__main__":
    unittest.main()
