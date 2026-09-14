import unittest

from tools.release_notes import extract_release_notes


class ReleaseNotesTests(unittest.TestCase):
    def test_extracts_only_the_matching_version(self):
        changelog = """# 日志

## [v1.6.0-dev.13] - 标题 - 2026-09-14

### 状态栏

- 当前版本内容

## [v1.6.0-dev.12] - 旧版

- 旧内容
"""
        notes = extract_release_notes(changelog, "1.6.0-dev.13")
        self.assertIn("当前版本内容", notes)
        self.assertNotIn("旧内容", notes)
        self.assertNotIn("v1.6.0-dev.12", notes)

    def test_missing_duplicate_or_invalid_versions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "实际为 0"):
            extract_release_notes("# 空", "1.6.0-dev.13")
        duplicate = "## [v1.6.0-dev.13] - A\n内容\n## [v1.6.0-dev.13] - B\n内容"
        with self.assertRaisesRegex(ValueError, "实际为 2"):
            extract_release_notes(duplicate, "1.6.0-dev.13")
        with self.assertRaisesRegex(ValueError, "无效版本号"):
            extract_release_notes("", "not a version")


if __name__ == "__main__":
    unittest.main()
