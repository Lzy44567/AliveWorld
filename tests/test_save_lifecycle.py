import json
import tempfile
import unittest
from pathlib import Path

from core.asset_lifecycle import AssetLifecycleError
from core.save_lifecycle import clone_save, rename_save


class SaveLifecycleTests(unittest.TestCase):
    def _make_save(self, root: Path, name="原故事") -> Path:
        save = root / "Save_original"
        (save / "characters").mkdir(parents=True)
        (save / "characters" / "角色.yml").write_text("name: 角色\n", encoding="utf-8")
        (save / "session_state.json").write_text(
            json.dumps({"save_name": name, "save_dir_path": str(save), "chat_messages": ["x"]}, ensure_ascii=False),
            encoding="utf-8",
        )
        return save

    def test_clone_is_independent_and_updates_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            source = self._make_save(Path(temp))
            target = clone_save(source, "故事分支")
            state = json.loads((target / "session_state.json").read_text(encoding="utf-8"))
            self.assertEqual("故事分支", state["save_name"])
            self.assertEqual(str(target), state["save_dir_path"])
            self.assertTrue((target / "characters" / "角色.yml").exists())
            (target / "characters" / "角色.yml").write_text("name: 新角色\n", encoding="utf-8")
            self.assertIn("角色", (source / "characters" / "角色.yml").read_text(encoding="utf-8"))

    def test_rename_moves_directory_and_updates_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            source = self._make_save(Path(temp))
            target = rename_save(source, "新故事")
            self.assertFalse(source.exists())
            self.assertTrue(target.exists())
            state = json.loads((target / "session_state.json").read_text(encoding="utf-8"))
            self.assertEqual("新故事", state["save_name"])

    def test_conflict_and_invalid_name_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self._make_save(root)
            (root / "Save_taken").mkdir()
            with self.assertRaises(AssetLifecycleError):
                clone_save(source, "taken")
            with self.assertRaises(AssetLifecycleError):
                rename_save(source, "bad/name")
