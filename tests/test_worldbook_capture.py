import tempfile
import unittest
from pathlib import Path

import yaml

from core.worldbook_capture import WorldbookCaptureService


class FakeAI:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def chat_json(self, *_args, **_kwargs):
        self.calls += 1
        return self.response, None


class WorldbookCaptureTests(unittest.TestCase):
    def write_book(self, directory, data=None):
        path = Path(directory) / "worldbooks" / "world.yml"
        path.parent.mkdir(parents=True)
        path.write_text(yaml.safe_dump(data or {"name": "世界", "entries": []}, allow_unicode=True), encoding="utf-8")
        return path

    def test_low_risk_candidate_is_added_automatically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self.write_book(temp_dir)
            ai = FakeAI('{"candidates":[{"name":"校服制度","content":"学生统一穿特殊校服","risk":"low","reason":"长期制度"}]}')
            result = WorldbookCaptureService(ai).capture(path, "进入学校", "学生们穿着统一校服。", review_all=False)
            self.assertEqual([item["name"] for item in result["added"]], ["校服制度"])
            saved = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertIn("AI推断", saved["entries"][0]["tags"])
            self.assertNotIn("待确认", saved["entries"][0]["tags"])

    def test_review_mode_and_high_risk_candidate_stay_pending(self):
        for review_all, risk in ((True, "low"), (False, "high")):
            with self.subTest(review_all=review_all, risk=risk), tempfile.TemporaryDirectory() as temp_dir:
                path = self.write_book(temp_dir)
                ai = FakeAI('{"candidates":[{"name":"新制度","content":"改变社会规则","risk":"%s"}]}' % risk)
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

    def test_schedule_skips_when_no_active_worldbook(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ai = FakeAI('{"candidates":[]}')
            self.assertFalse(WorldbookCaptureService(ai).schedule(temp_dir, "行动", "正文", review_all=False))
            self.assertEqual(ai.calls, 0)


if __name__ == "__main__":
    unittest.main()
