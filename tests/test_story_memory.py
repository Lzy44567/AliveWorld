import json
import tempfile
import time
import unittest
from pathlib import Path

from core.game_session import GameSession
from core.story_memory import MemoryBudget, StoryMemoryManager, estimate_tokens


class FakeMemoryAI:
    def __init__(self, payload=None, error=None):
        self.payload = payload or {
            "segment_summary": "玩家离开村庄并发现商队遇袭。",
            "chapter_spine": "玩家从村庄启程，开始调查商队失踪。",
            "story_events": [{
                "name": "调查失踪商队",
                "core_goal": "确认商队下落",
                "completion_condition": "商队成员的下落已经明确",
                "progress": "发现遇袭马车",
                "status": "active",
                "source_turns": [1, 2],
            }],
            "important_memories": ["村长委托玩家调查商队。"],
            "core_memories": [],
        }
        self.error = error
        self.calls = []

    def chat_json(self, system_prompt, user_prompt, **kwargs):
        self.calls.append((system_prompt, user_prompt, kwargs))
        if self.error:
            return "", self.error
        return json.dumps(self.payload, ensure_ascii=False), None


def turns(count=8, size=120):
    return [
        {
            "turn_id": index,
            "player": f"行动{index}",
            "story": "剧情" * size,
            "text": f"玩家：行动{index}\n结果：" + "剧情" * size,
        }
        for index in range(count)
    ]


class StoryMemoryTests(unittest.TestCase):
    def test_budget_is_derived_from_context_limit(self):
        budget = MemoryBudget.from_context_limit(32768)
        self.assertEqual(32768, budget.context_limit)
        self.assertGreater(budget.history_high_water, budget.history_low_water)
        self.assertGreater(budget.bridge_tokens, 0)
        self.assertGreater(estimate_tokens("中文 ABCD 1234。"), 4)

    def test_force_compaction_archives_complete_turns_and_keeps_hot_tail(self):
        with tempfile.TemporaryDirectory() as temp:
            ai = FakeMemoryAI()
            manager = StoryMemoryManager(temp, ai, context_limit=8192)
            source = turns()
            result = manager.compact_now(source, force=True)

            self.assertTrue(result["completed"])
            self.assertEqual(1, len(ai.calls))
            status = manager.status(source)
            self.assertGreaterEqual(status["segment_count"], 1)
            self.assertGreaterEqual(status["raw_turn_count"], 4)
            segment = Path(temp) / "memory" / "segments" / f"turn_{result['start_turn']:06d}-{result['end_turn']:06d}.json"
            self.assertTrue(segment.exists())
            payload = json.loads(segment.read_text(encoding="utf-8"))
            self.assertEqual(result["start_turn"], payload["turns"][0]["turn_id"])
            self.assertEqual(result["end_turn"], payload["turns"][-1]["turn_id"])

            context = manager.build_context(source, compression_enabled=True)
            self.assertIn("长期故事脊柱", context)
            self.assertIn("调查失踪商队", context)
            self.assertIn(f"【回合 {result['end_turn'] + 1}】", context)

    def test_failed_compaction_does_not_advance_index(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = StoryMemoryManager(temp, FakeMemoryAI(error="connection failed"), context_limit=8192)
            result = manager.compact_now(turns(), force=True)
            self.assertFalse(result["completed"])
            self.assertEqual(-1, manager.status(turns())["archived_until_turn"])
            self.assertFalse((Path(temp) / "memory" / "index.json").exists())

    def test_automatic_compaction_does_not_call_model_below_watermark(self):
        with tempfile.TemporaryDirectory() as temp:
            ai = FakeMemoryAI()
            manager = StoryMemoryManager(temp, ai, context_limit=8192)
            self.assertFalse(manager.schedule(turns(3, 10), enabled=True))
            self.assertEqual([], ai.calls)

            manager.budget = MemoryBudget(8192, 300, 150, 50, 2)
            self.assertTrue(manager.schedule(turns(8, 120), enabled=True))
            deadline = time.monotonic() + 2
            while manager.status(turns(8, 120))["running"] and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(1, len(ai.calls))
            self.assertEqual(1, manager.status(turns(8, 120))["segment_count"])

    def test_disabled_mode_preserves_legacy_last_three_turn_context(self):
        manager = StoryMemoryManager(context_limit=8192)
        context = manager.build_context(turns(6, 10), compression_enabled=False)
        self.assertNotIn("【回合 2】", context)
        self.assertIn("【回合 3】", context)
        self.assertIn("【回合 5】", context)

    def test_memory_injection_has_its_own_budget(self):
        manager = StoryMemoryManager(context_limit=8192)
        manager.index["core_memories"] = ["核心" * 1000 for _ in range(10)]
        manager.index["chapter_spine"] = "历史" * 10000
        rendered = manager._render_memory()
        self.assertLessEqual(estimate_tokens(rendered), 1502)

    def test_session_rollback_restores_story_turns(self):
        with tempfile.TemporaryDirectory() as temp:
            session = GameSession(None, "测试", temp)
            session.start_new_game("", "开场")
            session._take_snapshot()
            session.story_memory.append_turn(session.history["story_turns"], "前进", "抵达广场")
            self.assertEqual(2, len(session.history["story_turns"]))
            self.assertTrue(session.rollback())
            self.assertEqual(1, len(session.history["story_turns"]))


if __name__ == "__main__":
    unittest.main()
