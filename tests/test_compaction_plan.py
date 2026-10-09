import copy
import unittest

from core.compaction_plan import plan_compaction
from core.story_memory import MemoryBudget, StoryMemoryManager


def units(*costs):
    return [{'id': i, 'token_estimate': cost, 'text': ['original']} for i, cost in enumerate(costs)]


def plan(values, **options):
    return plan_compaction(values, **({'high_water': 500, 'low_water': 250,
                                     'min_hot_units': 2, 'bridge_tokens': 100} | options))


class CompactionPlanTests(unittest.TestCase):
    def test_empty_single_and_threshold(self):
        self.assertIsNone(plan([]))
        self.assertIsNone(plan(units(800)))
        self.assertIsNone(plan(units(249, 250)))
        self.assertEqual(250, plan(units(250, 250))['archived_tokens'])
        self.assertEqual(251, plan(units(251, 250))['archived_tokens'])

    def test_whole_prefix_and_hot_tail(self):
        value = plan(units(100, 100, 100, 100, 100, 100))
        self.assertEqual([0, 1, 2, 3], [i['id'] for i in value['archive']])
        self.assertEqual(200, value['remaining_tokens'])
        self.assertEqual([4], [i['id'] for i in value['bridge']])

    def test_force_minimum(self):
        self.assertIsNone(plan(units(149, 150, 1, 1), force=True))
        self.assertEqual(300, plan(units(150, 150, 1, 1), force=True)['archived_tokens'])

    def test_large_unit_and_bridge_boundary(self):
        value = plan(units(900, 60, 60, 60, 60))
        self.assertEqual([0], [i['id'] for i in value['archive']])
        self.assertEqual([1, 2], [i['id'] for i in value['bridge']])
        value = plan(units(900, 200, 200))
        self.assertEqual([0, 1], [i['id'] for i in value['archive']])
        self.assertEqual([2], [i['id'] for i in value['bridge']])

    def test_input_and_output_are_independent(self):
        source = units(200, 200, 200, 200)
        before = copy.deepcopy(source)
        value = plan(source)
        value['archive'][0]['text'].append('changed')
        value['bridge'][0]['text'].append('changed')
        self.assertEqual(before, source)

    def test_story_adapter_preserves_return(self):
        manager = StoryMemoryManager()
        manager.budget = MemoryBudget(8192, 500, 250, 100, 2)
        source = units(200, 200, 200, 200)
        manager._raw_turns = lambda _: source
        for force in (False, True):
            self.assertEqual(plan(source, force=force), manager._plan([], force=force))
