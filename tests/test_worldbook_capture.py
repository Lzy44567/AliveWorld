import tempfile
import unittest
from pathlib import Path

import yaml

from core.world_rule_commands import world_rule_command_mode
from core.worldbook_capture import WorldbookCaptureService, capture_requested


class FakeAI:
    def __init__(self, response):
        self.response = response
        self.calls = 0
        self.last_system_prompt = ""
        self.last_user_prompt = ""

    def chat_json(self, system_prompt, user_prompt, **_kwargs):
        self.calls += 1
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        return self.response, None


class WorldbookCaptureTests(unittest.TestCase):
    def test_capture_requires_explicit_boolean_true(self):
        self.assertTrue(capture_requested({"worldbook_capture_needed": True}))
        self.assertFalse(capture_requested({"worldbook_capture_needed": False}))
        self.assertFalse(capture_requested({"worldbook_capture_needed": "true"}))
        self.assertFalse(capture_requested({}))
        self.assertFalse(capture_requested(None))
        self.assertTrue(capture_requested({"worldbook_capture_needed": False}, "常识改变：所有人认为蓝雨很正常"))
        self.assertTrue(capture_requested({}, "常识恢复"))
        self.assertFalse(capture_requested({}, "我们讨论了一部常识改变题材的漫画"))

    def test_common_sense_command_detection_is_explicit(self):
        self.assertEqual(world_rule_command_mode("常识改变：公众裸体是正常礼仪"), "change")
        self.assertEqual(world_rule_command_mode("常识恢复：公众礼仪"), "restore")
        self.assertEqual(world_rule_command_mode("我想研究常识改变题材"), "")

    def write_book(self, directory, data=None):
        path = Path(directory) / "worldbooks" / "world.yml"
        path.parent.mkdir(parents=True)
        path.write_text(yaml.safe_dump(data or {"name": "世界", "entries": []}, allow_unicode=True), encoding="utf-8")
        return path

    def test_low_risk_candidate_is_added_automatically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self.write_book(temp_dir)
            ai = FakeAI('{"candidates":[{"name":"校服制度","content":"学生统一穿特殊校服","risk":"low","scope":"social_system","confidence":"high","reason":"长期制度"}]}')
            result = WorldbookCaptureService(ai).capture(path, "进入学校", "学生们穿着统一校服。", review_all=False)
            self.assertEqual([item["name"] for item in result["added"]], ["校服制度"])
            saved = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertIn("AI推断", saved["entries"][0]["tags"])
            self.assertNotIn("待确认", saved["entries"][0]["tags"])

    def test_common_sense_change_command_adds_a_confirmed_rule_and_marks_origin(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self.write_book(temp_dir)
            ai = FakeAI('{"candidates":[{"operation":"add","name":"蓝雨常识","content":"此后所有自然降雨呈蓝色","risk":"low","scope":"natural_law","confidence":"high","reason":"玩家的改变已在正文中生效"}]}')
            result = WorldbookCaptureService(ai).capture(
                path, "常识改变：从现在起自然降雨是蓝色", "天空落下蓝色雨滴，所有人都将其视为一直如此。", review_all=False,
            )
            self.assertEqual([item["name"] for item in result["added"]], ["蓝雨常识"])
            self.assertIn("常识改变", result["added"][0]["tags"])

    def test_common_sense_restore_can_only_update_or_retire_an_existing_change(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self.write_book(temp_dir, {"name": "世界", "entries": [{"id": "entry_blue", "name": "蓝雨常识", "content": "自然降雨呈蓝色", "tags": ["常识改变"]}]})
            ai = FakeAI('{"candidates":[{"operation":"retire","target_entry_id":"entry_blue","name":"蓝雨常识","content":"自然降雨呈蓝色","risk":"low","scope":"natural_law","confidence":"high","reason":"常识恢复已生效"}]}')
            result = WorldbookCaptureService(ai).capture(path, "常识恢复：自然降雨", "人们恢复了雨水原本无色的常识。", review_all=False)
            self.assertEqual(result["added"], [])
            self.assertEqual(result["pending"][0]["pending_operation"], "retire")
            self.assertIn("常识恢复", result["pending"][0]["tags"])

    def test_common_sense_restore_rejects_a_new_entry_even_if_model_proposes_one(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self.write_book(temp_dir)
            ai = FakeAI('{"candidates":[{"operation":"add","name":"恢复事件","content":"大家恢复常识","risk":"low","scope":"social_system","confidence":"high"}]}')
            result = WorldbookCaptureService(ai).capture(path, "常识恢复", "能力生效", review_all=False)
            self.assertEqual(result["added"], [])
            self.assertEqual(result["pending"], [])

    def test_existing_rule_update_and_retirement_wait_for_player_confirmation(self):
        for operation in ("update", "retire"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temp_dir:
                path = self.write_book(temp_dir, {"name": "世界", "entries": [{"id": "entry_old", "name": "旧常识", "content": "雨是透明的"}]})
                ai = FakeAI('{"candidates":[{"operation":"%s","target_entry_id":"entry_old","name":"旧常识","content":"雨变成蓝色","risk":"low","scope":"natural_law","confidence":"high","reason":"玩家明确改变"}]}' % operation)
                result = WorldbookCaptureService(ai).capture(path, "改变常识", "规则改变生效", review_all=False)
                self.assertEqual(result["added"], [])
                self.assertEqual(len(result["pending"]), 1)
                proposal = result["pending"][0]
                self.assertNotEqual(proposal["id"], "entry_old")
                self.assertEqual(proposal["pending_operation"], operation)
                self.assertEqual(proposal["replaces_entry_id"], "entry_old")
                saved = yaml.safe_load(path.read_text(encoding="utf-8"))
                self.assertEqual(saved["entries"][0]["content"], "雨是透明的")
                self.assertIn("待确认", saved["entries"][1]["tags"])

    def test_review_mode_and_high_risk_candidate_stay_pending(self):
        for review_all, risk in ((True, "low"), (False, "high")):
            with self.subTest(review_all=review_all, risk=risk), tempfile.TemporaryDirectory() as temp_dir:
                path = self.write_book(temp_dir)
                ai = FakeAI('{"candidates":[{"name":"新制度","content":"改变社会规则","risk":"%s","scope":"social_system","confidence":"high"}]}' % risk)
                result = WorldbookCaptureService(ai).capture(path, "行动", "正文", review_all=review_all)
                self.assertEqual(len(result["pending"]), 1)
                self.assertIn("待确认", result["pending"][0]["tags"])

    def test_duplicate_and_dynamic_noise_are_not_written_by_protocol_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self.write_book(temp_dir, {"name": "世界", "entries": [{"name": "法律", "content": "现有法律"}]})
            ai = FakeAI('{"candidates":[{"name":"法律","content":"重复内容","risk":"low"}]}')
            result = WorldbookCaptureService(ai).capture(path, "行动", "正文", review_all=False)
            self.assertEqual(result["added"], [])
            self.assertEqual(len(yaml.safe_load(path.read_text(encoding="utf-8"))["entries"]), 1)

    def test_item_location_and_entity_candidates_require_review(self):
        for scope in ("unique_item", "stable_location", "character_entity"):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as temp_dir:
                path = self.write_book(temp_dir)
                ai = FakeAI('{"candidates":[{"name":"单回合发现","content":"看起来具有特殊功能","risk":"low","scope":"%s","confidence":"high"}]}' % scope)
                result = WorldbookCaptureService(ai).capture(path, "调查", "发现某物", review_all=False)
                self.assertEqual(result["added"], [])
                self.assertEqual(len(result["pending"]), 1)
                self.assertIn("待确认", result["pending"][0]["tags"])

    def test_missing_scope_or_confidence_requires_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self.write_book(temp_dir)
            ai = FakeAI('{"candidates":[{"name":"模糊设定","content":"可能长期存在","risk":"low"}]}')
            result = WorldbookCaptureService(ai).capture(path, "行动", "正文", review_all=False)
            self.assertEqual(result["added"], [])
            self.assertEqual(len(result["pending"]), 1)

    def test_event_detail_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self.write_book(temp_dir)
            ai = FakeAI('{"candidates":[{"name":"本回合爆炸","content":"木屋刚刚被炸毁","risk":"low","scope":"event_detail","confidence":"high"}]}')
            result = WorldbookCaptureService(ai).capture(path, "爆炸", "木屋被炸毁", review_all=False)
            self.assertEqual(result["added"], [])
            self.assertEqual(result["pending"], [])
            self.assertEqual(len(yaml.safe_load(path.read_text(encoding="utf-8"))["entries"]), 0)

    def test_schedule_creates_a_fallback_when_no_worldbook_exists(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp_dir:
            ai = FakeAI('{"candidates":[]}')
            with patch('core.worldbook_capture.threading.Thread') as thread:
                thread.side_effect = lambda **kw: type('InlineThread', (), {'start': lambda self: kw['target'](*kw['args'], **kw['kwargs'])})()
                self.assertTrue(WorldbookCaptureService(ai).schedule(temp_dir, "行动", "正文", review_all=False))
            self.assertEqual(len(list((Path(temp_dir) / "worldbooks").glob("*.yml"))), 1)

    def test_command_rules_are_only_added_to_the_capture_request_when_triggered(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self.write_book(temp_dir)
            ai = FakeAI('{"candidates":[]}')
            service = WorldbookCaptureService(ai)
            service.capture(path, "普通行动", "普通正文", review_all=False)
            self.assertNotIn("显式规则变更命令", ai.last_user_prompt)
            service.capture(path, "常识改变：雨是蓝色", "改变生效", review_all=False)
            self.assertIn("显式规则变更命令", ai.last_user_prompt)


if __name__ == "__main__":
    unittest.main()
