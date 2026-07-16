import unittest

from core.story_events import StoryEventLedger


class StoryEventLedgerTests(unittest.TestCase):
    def test_reconcile_reuses_event_and_requires_completion_evidence(self):
        ledger = StoryEventLedger()
        created = ledger.reconcile([{
            "name": "调查失踪商队",
            "core_goal": "确认商队下落",
            "completion_condition": "已经确认商队成员的最终下落",
            "progress": "发现马车残骸",
            "status": "active",
            "source_turns": [2, 4],
        }], current_turn=4)[0]

        ledger.reconcile([{
            "id": created.id,
            "name": created.name,
            "core_goal": "模型擅自改变的目标",
            "completion_condition": "模型擅自放宽的条件",
            "status": "completed",
            "progress": "找到了幸存者",
        }], current_turn=8)
        self.assertEqual("active", ledger.by_id(created.id).status)

        ledger.reconcile([{
            "id": created.id,
            "name": created.name,
            "status": "completed",
            "progress": "找到了幸存者",
            "completion_evidence": "正文明确写明所有商队成员的下落已经确认",
        }], current_turn=9)
        restored = ledger.by_id(created.id)
        self.assertEqual("completed", restored.status)
        self.assertEqual("确认商队下落", restored.core_goal)
        self.assertEqual("已经确认商队成员的最终下落", restored.completion_condition)
        self.assertEqual(4, restored.created_turn)
        self.assertEqual(5, restored.age_turns)

    def test_invalid_or_empty_event_is_not_created(self):
        ledger = StoryEventLedger()
        self.assertEqual([], ledger.reconcile([{"name": "推进剧情", "core_goal": ""}], current_turn=1))
        self.assertEqual([], ledger.export())


if __name__ == "__main__":
    unittest.main()
