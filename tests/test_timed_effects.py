import copy
import unittest

from core.state_manager import StateManager


def poisoned(health=100):
    manager = StateManager()
    manager.state['bars']['生命'] = {'current': health, 'max': 100, 'change': 0}
    manager.state['buffs']['毒'] = {'生命_per_turn': -5, 'duration': 5}
    return manager


class TimedEffectTests(unittest.TestCase):
    def test_five_rounds_and_expiry(self):
        manager = poisoned()
        plan, progress = manager.plan_effects(5)
        self.assertEqual(plan.state['bars']['生命']['current'], 75)
        self.assertEqual(plan.state['buffs'], {})
        self.assertEqual(progress.completed_rounds, 5)
        self.assertIsNone(progress.stopped_bar)

    def test_preview_does_not_mutate_live_or_alias_it(self):
        manager = poisoned()
        before = copy.deepcopy(manager.state)
        plan, _ = manager.plan_effects(2)
        self.assertEqual(manager.state, before)
        manager.commit(plan)
        plan.state['bars']['生命']['current'] = 0
        self.assertEqual(manager.state['bars']['生命']['current'], 90)

    def test_leaving_after_two_rounds_only_has_three_remaining(self):
        manager = poisoned()
        plan, _ = manager.plan_effects(2)
        manager.commit(plan)
        plan, _ = manager.plan_effects(1000000)
        self.assertEqual(plan.state['bars']['生命']['current'], 75)
        self.assertEqual(plan.state['buffs'], {})

    def test_critical_threshold_interrupts_before_later_healing(self):
        manager = poisoned(8)
        manager.state['buffs']['慢愈'] = {'生命_per_turn': 1, 'duration': -1}
        plan, progress = manager.plan_effects(100, stop_at_zero=('生命',))
        self.assertEqual(progress.completed_rounds, 2)
        self.assertEqual(progress.stopped_bar, '生命')
        self.assertEqual(plan.state['bars']['生命']['current'], 0)
        self.assertEqual(manager.state['bars']['生命']['current'], 8)

    def test_zero_rounds_does_not_consume(self):
        plan, progress = poisoned().plan_effects(0)
        self.assertEqual(plan.state['buffs']['毒']['duration'], 5)
        self.assertEqual(progress.completed_rounds, 0)

    def test_invalid_rounds_fail_before_live_changes(self):
        for rounds in (True, -1, 1.5, '5'):
            manager = poisoned()
            before = copy.deepcopy(manager.state)
            with self.assertRaises(ValueError):
                manager.plan_effects(rounds)
            self.assertEqual(manager.state, before)

    def test_composing_settlement_does_not_tick_twice(self):
        manager = poisoned()
        effects, _ = manager.plan_effects(2)
        final = manager.plan_updates(
            {'dynamic_bars': {'生命': {'change': -3}}}, effect_plan=effects,
        )
        self.assertEqual(final.state['bars']['生命']['current'], 87)
        self.assertEqual(final.state['bars']['生命']['change'], -13)
        self.assertEqual(final.state['buffs']['毒']['duration'], 3)
        self.assertEqual(effects.state['bars']['生命']['current'], 90)

    def test_new_effect_is_not_backdated_over_elapsed_rounds(self):
        manager = poisoned()
        effects, _ = manager.plan_effects(5)
        final = manager.plan_updates(
            {'new_buffs': {'灼烧': {'生命_per_turn': -2, 'duration': 3}}},
            effect_plan=effects,
        )
        self.assertEqual(final.state['bars']['生命']['current'], 75)
        self.assertEqual(final.state['buffs']['灼烧']['duration'], 3)

    def test_legacy_new_buff_still_ticks_on_creation(self):
        manager = poisoned()
        manager.state['buffs'] = {}
        manager.apply_updates({'new_buffs': {'毒': {'生命_per_turn': -5, 'duration': 5}}})
        self.assertEqual(manager.state['bars']['生命']['current'], 95)
        self.assertEqual(manager.state['buffs']['毒']['duration'], 4)

    def test_restore_snapshot_restores_progress(self):
        manager = poisoned()
        snapshot = copy.deepcopy(manager.state)
        plan, _ = manager.plan_effects(5)
        manager.commit(plan)
        manager.state = copy.deepcopy(snapshot)
        again, _ = manager.plan_effects(1)
        self.assertEqual(again.state['bars']['生命']['current'], 95)
        self.assertEqual(again.state['buffs']['毒']['duration'], 4)


if __name__ == '__main__':
    unittest.main()
