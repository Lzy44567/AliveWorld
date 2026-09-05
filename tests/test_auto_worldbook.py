import tempfile
import unittest
from pathlib import Path

import yaml

from core.auto_worldbook import ensure_auto_capture_worldbook, select_capture_worldbook


class AutoWorldbookTests(unittest.TestCase):
    def test_blank_story_gets_one_save_local_editable_book(self):
        with tempfile.TemporaryDirectory() as temporary:
            save = Path(temporary) / "Save_blank"
            path = ensure_auto_capture_worldbook(save)
            again = ensure_auto_capture_worldbook(save)
            data = yaml.safe_load(path.read_text(encoding="utf-8"))

            self.assertEqual(path, again)
            self.assertEqual(path.parent, save / "worldbooks")
            self.assertEqual(data["name"], "本局自动设定")
            self.assertTrue(data["is_auto_capture_book"])
            self.assertTrue(data["is_active"])
            self.assertEqual(data["entries"], [])
            self.assertEqual(len(list((save / "worldbooks").glob("*.yml"))), 1)

    def test_authored_active_book_is_preferred_over_automatic_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            save = Path(temporary) / "Save_test"
            automatic = ensure_auto_capture_worldbook(save)
            authored = save / "worldbooks" / "world.yml"
            authored.write_text(
                yaml.safe_dump({"name": "作者世界书", "entries": [], "is_active": True}, allow_unicode=True),
                encoding="utf-8",
            )

            self.assertEqual(select_capture_worldbook(save), authored)
            authored.write_text(
                yaml.safe_dump({"name": "作者世界书", "entries": [], "is_active": False}, allow_unicode=True),
                encoding="utf-8",
            )
            self.assertEqual(select_capture_worldbook(save), automatic)

    def test_existing_authored_book_suppresses_fallback_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            save = Path(temporary) / "Save_package"
            directory = save / "worldbooks"
            directory.mkdir(parents=True)
            authored = directory / "package.yml"
            authored.write_text(
                yaml.safe_dump({"name": "世界包设定", "entries": [], "is_active": True}, allow_unicode=True),
                encoding="utf-8",
            )

            self.assertEqual(select_capture_worldbook(save, create_fallback=True), authored)
            self.assertEqual(list(directory.glob("*.yml")), [authored])


if __name__ == "__main__":
    unittest.main()
