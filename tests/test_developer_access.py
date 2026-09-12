import json
import tempfile
import unittest
from pathlib import Path

from core.developer_access import DeveloperAccess


class DeveloperAccessTests(unittest.TestCase):
    def test_password_is_hashed_and_token_is_ephemeral(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "access.json"
            access = DeveloperAccess(path)
            token = access.setup("correct-horse")
            access.require(token)
            contents = path.read_text(encoding="utf-8")
            self.assertNotIn("correct-horse", contents)
            self.assertEqual(json.loads(contents)["algorithm"], "pbkdf2-sha256")
            access.lock(token)
            with self.assertRaises(PermissionError):
                access.require(token)
            access.require(access.unlock("correct-horse"))

    def test_short_and_wrong_passwords_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            access = DeveloperAccess(Path(temporary) / "access.json")
            with self.assertRaisesRegex(ValueError, "8 个字符"):
                access.setup("short")
            access.setup("long-enough")
            with self.assertRaisesRegex(PermissionError, "密码错误"):
                access.unlock("not-correct")


if __name__ == "__main__":
    unittest.main()
