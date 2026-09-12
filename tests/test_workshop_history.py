import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.workshop_history import published_history


class WorkshopHistoryTests(unittest.TestCase):
    def test_returns_only_matching_published_safe_conversation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            for name in ("published", "draft", "other"):
                (directory / f"{name}.json").write_text(json.dumps({"id": name}), encoding="utf-8")
            sessions = {
                "published": SimpleNamespace(
                    id="published", published=True, target="wanted", updated_at="2026-09-12T12:00:00+00:00",
                    messages=[
                        {"role": "user", "content": "保留玩家讨论", "private": "discard"},
                        {"role": "ai", "content": "保留工坊回答"},
                        {"role": "system", "content": "不导出内部消息"},
                    ],
                ),
                "draft": SimpleNamespace(id="draft", published=False, target="wanted", updated_at="", messages=[]),
                "other": SimpleNamespace(id="other", published=True, target="other", updated_at="", messages=[]),
            }
            result = published_history(directory, sessions.get, lambda item: item.target == "wanted")
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["workshop_id"], "published")
            self.assertEqual(result[0]["messages"], [
                {"role": "user", "content": "保留玩家讨论"},
                {"role": "assistant", "content": "保留工坊回答"},
            ])
            self.assertNotIn("draft", result[0])


if __name__ == "__main__":
    unittest.main()
