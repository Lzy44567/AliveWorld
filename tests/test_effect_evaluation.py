import copy
import unittest

from tools.testing.evaluate_timed_effects import check_state


class EffectEvaluationTests(unittest.TestCase):
    def test_correct_health_alone_does_not_pass_wrong_clock(self):
        state = {'bars': {'生命': {'current': 95}},
                 'buffs': {'毒': {'duration': 4, 'tick_elapsed': 0}}}
        report = {'mode': 'seconds', 'applied': 10, 'interrupted': False}
        checks = check_state('short', state, report)
        self.assertTrue(checks['health'])
        self.assertFalse(checks['elapsed'])
        self.assertFalse(checks['remainder'])

    def test_all_three_numeric_cases_check_progress_without_mutation(self):
        for name, hp, seconds, duration, remainder, interrupted in (
            ('short', 95, 15, 4, 5, False),
            ('critical', 0, 20, 3, 0, True),
            ('no_time', 100, 0, 5, 0, False),
        ):
            state = {'bars': {'生命': {'current': hp}},
                     'buffs': {'毒': {'duration': duration, 'tick_elapsed': remainder}}}
            before = copy.deepcopy(state)
            report = {'mode': 'seconds', 'applied': seconds, 'interrupted': interrupted}
            self.assertTrue(all(check_state(name, state, report).values()))
            self.assertEqual(state, before)
