import io
import json
import unittest
import zipfile
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.feedback.models import FeedbackDraft
from core.feedback.redaction import contains_suspected_secret, redact
from core.feedback.service import build_diagnostic_zip, build_feedback_preview
from main import create_app


SAMPLE_LOG = {
    "id": "event-1", "time": "12:34:56", "level": "error", "category": "story",
    "category_label": "正文", "task": "剧情结算", "trace_id": "trace-abc",
    "phase": "response", "status": "failed", "summary": "请求失败",
    "details": {"authorization": "Bearer real-secret", "story": "玩家私人正文"},
}


class FeedbackRedactionTests(unittest.TestCase):
    def test_redacts_credentials_and_user_profile(self):
        value = redact({
            "api_key": "sk-very-secret-value",
            "text": r"C:\Users\Alice\story Bearer token-value",
        })
        self.assertEqual(value["api_key"], "***")
        self.assertNotIn("Alice", value["text"])
        self.assertNotIn("token-value", value["text"])
        self.assertFalse(contains_suspected_secret(value))

    @patch("core.feedback.service._recent_events", return_value=[SAMPLE_LOG])
    def test_unselected_log_details_never_enter_preview(self, _mocked):
        preview = build_feedback_preview(FeedbackDraft(title="测试", actual="失败"))
        self.assertEqual(preview["selected_logs"], [])
        self.assertNotIn("玩家私人正文", preview["markdown"])

    @patch("core.feedback.service._recent_events", return_value=[SAMPLE_LOG])
    def test_selected_log_is_redacted_and_packaged_by_whitelist(self, _mocked):
        content, filename = build_diagnostic_zip(FeedbackDraft(
            title="测试", actual="失败", selected_log_ids=["event-1"],
        ))
        self.assertTrue(filename.endswith(".zip"))
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {"feedback.md", "environment.json", "manifest.json", "logs.jsonl"},
            )
            logs = archive.read("logs.jsonl").decode("utf-8")
            self.assertIn("玩家私人正文", logs)
            self.assertNotIn("real-secret", logs)
            manifest = json.loads(archive.read("manifest.json"))
            self.assertTrue(manifest["contains_story_content"])


class FeedbackRouteTests(unittest.TestCase):
    def test_preview_and_export_work_without_network(self):
        client = TestClient(create_app(frontend_dist="missing"))
        payload = {"category": "bug", "title": "按钮失效", "actual": "没有响应", "expected": "正常响应"}
        preview = client.post("/api/v1/feedback/preview", json=payload)
        self.assertEqual(preview.status_code, 200)
        self.assertIn("按钮失效", preview.json()["markdown"])
        exported = client.post("/api/v1/feedback/export", json=payload)
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported.headers["content-type"], "application/zip")
        with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
            self.assertIn("feedback.md", archive.namelist())


if __name__ == "__main__":
    unittest.main()
