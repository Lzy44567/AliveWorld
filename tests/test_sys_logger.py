import logging
import json
import tempfile
import unittest
from pathlib import Path

from utils.sys_logger import CustomFormatter, StructuredFormatter, classify_log, read_logs_structured, redact_log_value


class SysLoggerTests(unittest.TestCase):
    def test_formatter_keeps_exception_details(self):
        try:
            raise RuntimeError("diagnostic detail")
        except RuntimeError:
            record = logging.LogRecord(
                name="AliveWorld",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg="startup failed",
                args=(),
                exc_info=__import__("sys").exc_info(),
            )

        formatted = CustomFormatter().format(record)
        self.assertIn("startup failed", formatted)
        self.assertIn("RuntimeError: diagnostic detail", formatted)

    def test_structured_formatter_classifies_redacts_and_preserves_trace(self):
        record = logging.LogRecord(
            name="AliveWorld", level=logging.INFO, pathname=__file__, lineno=1,
            msg="LLM 请求 [生图提示词编译] id=abc", args=(), exc_info=None,
        )
        record.aw_task = "生图提示词编译"
        record.aw_trace_id = "abc123"
        record.aw_phase = "request"
        record.aw_status = "sent"
        record.aw_details = {"api_key": "secret", "path": r"C:\Users\Alice\private.txt", "authorization": "Bearer token"}
        payload = json.loads(StructuredFormatter().format(record))
        self.assertEqual(payload["category"], "image")
        self.assertEqual(payload["trace_id"], "abc123")
        self.assertEqual(payload["details"]["api_key"], "***")
        self.assertIn("%USERPROFILE%", payload["details"]["path"])
        self.assertEqual(payload["details"]["authorization"], "***")

    def test_category_mapping_covers_core_model_tasks(self):
        self.assertEqual(classify_log("剧情结算"), "story")
        self.assertEqual(classify_log("变数推演"), "future")
        self.assertEqual(classify_log("Overseer实体推演"), "undercurrent")
        self.assertEqual(classify_log("世界书工坊"), "workshop")
        self.assertEqual(classify_log("故事记忆压缩"), "memory")

    def test_explicit_task_label_wins_over_prompt_content(self):
        self.assertEqual(classify_log("剧情结算", "提示词中包含用户偏好和世界书"), "story")
        self.assertEqual(classify_log("Overseer实体推演", "上下文中包含故事记忆"), "undercurrent")
        self.assertEqual(classify_log("变数推演", "读取世界书与暗流因果"), "future")

    def test_structured_reader_filters_category_and_trace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "run.jsonl"
            rows = [
                {"id":"1", "category":"story", "trace_id":"a"},
                {"id":"2", "category":"image", "trace_id":"b"},
                {"id":"3", "category":"story", "trace_id":"b"},
            ]
            path.write_text("\n".join(json.dumps(item) for item in rows), encoding="utf-8")
            self.assertEqual([item["id"] for item in read_logs_structured(category="story", log_dir=temp_dir)], ["1", "3"])
            self.assertEqual([item["id"] for item in read_logs_structured(trace_id="b", log_dir=temp_dir)], ["2", "3"])

    def test_redaction_masks_inline_credentials(self):
        value = redact_log_value("api_key=abcdef Bearer token123 sk-abcdefghijk")
        self.assertNotIn("abcdef", value)
        self.assertNotIn("token123", value)
        self.assertNotIn("abcdefghijk", value)


if __name__ == "__main__":
    unittest.main()
