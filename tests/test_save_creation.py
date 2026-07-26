import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from api.v1 import game_routes
from utils import file_io


class SaveCreationTests(unittest.TestCase):
    def test_init_save_folder_rejects_existing_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            save_root = Path(temporary)
            with patch.object(file_io, "SAVE_DIR", str(save_root)):
                created = Path(file_io.init_save_folder("同名测试"))
                self.assertTrue(created.is_dir())
                with self.assertRaises(FileExistsError):
                    file_io.init_save_folder("同名测试")

    def test_start_route_reports_duplicate_name(self):
        with (
            patch.object(game_routes, "global_ai_engine", object()),
            patch.object(game_routes, "init_save_folder", side_effect=FileExistsError),
        ):
            with self.assertRaises(HTTPException) as raised:
                game_routes.start_game(game_routes.StartRequest(save_name="旧故事"))

        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("已存在同名存档", raised.exception.detail)
        self.assertIn("旧故事", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
