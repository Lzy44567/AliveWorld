import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.image_generation.library import list_library_scopes, resolve_library_scope


class ImageLibraryTests(unittest.TestCase):
    def test_discovers_global_and_save_scopes_without_active_session(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            global_root = root / "global_images"
            save_root = root / "Save_Test"
            save_root.mkdir()
            with patch("core.image_generation.library.GLOBAL_IMAGE_LIBRARY_DIR", global_root), patch(
                "core.image_generation.library.get_all_saves",
                return_value={"测试存档": {"_save_dir": str(save_root)}},
            ):
                scopes = list_library_scopes()
                self.assertEqual([(item.id, item.kind) for item in scopes], [("global", "global"), ("Save_Test", "save")])
                self.assertEqual(resolve_library_scope("Save_Test").name, "测试存档")

    def test_unknown_scope_is_rejected(self):
        with patch("core.image_generation.library.get_all_saves", return_value={}):
            with self.assertRaises(ValueError):
                resolve_library_scope("missing")


if __name__ == "__main__":
    unittest.main()
