import unittest

from core.npc_presence import NpcPresenceTracker
from core.state_manager import StateManager


class NpcPresenceTests(unittest.TestCase):
    def test_departed_and_not_appearing_characters_do_not_enter_radar(self):
        tracker = NpcPresenceTracker()
        current = tracker.reconcile({}, {"路人": "已离开", "门外访客": "未出现"}, story_text="房间恢复安静")
        self.assertEqual(current, {})

    def test_unmentioned_npc_expires_after_three_turns_but_history_is_untouched(self):
        tracker = NpcPresenceTracker(stale_turns=3)
        current = tracker.reconcile({}, {"看守": "持有对讲机"}, story_text="看守站在门边")
        self.assertIn("看守", current)
        current = tracker.reconcile(current, {"看守": "持有对讲机"}, story_text="玩家进入地下室")
        self.assertIn("看守", current)
        current = tracker.reconcile(current, {"看守": "持有对讲机"}, story_text="玩家检查发电机")
        self.assertIn("看守", current)
        current = tracker.reconcile(current, {"看守": "持有对讲机"}, story_text="玩家拆下保险丝")
        self.assertNotIn("看守", current)

    def test_mention_resets_absence_and_metadata_round_trips(self):
        tracker = NpcPresenceTracker(stale_turns=3)
        current = tracker.reconcile({}, {"阿泰": "巡逻"}, story_text="阿泰走进宿舍")
        current = tracker.reconcile(current, {}, story_text="宿舍暂时安静")
        current = tracker.reconcile(current, {"阿泰": "返回门口"}, story_text="阿泰重新出现")
        self.assertEqual(current["阿泰"], "返回门口")
        restored = NpcPresenceTracker()
        restored.load_state(tracker.export_state())
        self.assertEqual(restored.absent_turns, tracker.absent_turns)

    def test_state_manager_uses_scene_text_instead_of_accumulating_stale_updates(self):
        manager = StateManager()
        manager.apply_updates({"npc_states": {"保安": "在门口"}}, story_text="保安拦住玩家")
        for text in ("玩家进入电梯", "玩家回到家中", "玩家关上房门"):
            manager.apply_updates({"npc_states": {"保安": "仍在旧地点"}}, story_text=text)
        self.assertEqual(manager.state["npcs"], {})

    def test_explicit_deletion_clears_visible_state_and_presence_metadata(self):
        manager = StateManager()
        manager.apply_updates({"npc_states": {"路人": "在场"}}, story_text="路人经过")
        manager.apply_updates({"status_deletions": ["路人"]}, story_text="街道空了")
        self.assertNotIn("路人", manager.state["npcs"])
        self.assertNotIn("路人", manager.export_metadata()["npc_presence"]["absent_turns"])


if __name__ == "__main__":
    unittest.main()
