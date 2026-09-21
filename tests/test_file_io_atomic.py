import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.file_io import save_game_data


class AtomicSaveTests(unittest.TestCase):
    def test_failed_serialization_preserves_previous_save_and_removes_temp_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "session_state.json"
            target.write_text(json.dumps({"turn": 1}), encoding="utf-8")

            with patch("utils.file_io.json.dump", side_effect=RuntimeError("serialization failed")):
                with self.assertRaisesRegex(RuntimeError, "serialization failed"):
                    save_game_data(str(root), {"turn": 2})

            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"turn": 1})
            self.assertEqual(list(root.glob(".session_state_*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
