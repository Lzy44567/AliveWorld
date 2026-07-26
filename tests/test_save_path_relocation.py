import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api.v1 import game_routes
from core.game_session import GameSession


class SavePathRelocationTests(unittest.TestCase):
    def tearDown(self):
        game_routes.active_sessions.clear()

    def test_session_load_prefers_current_runtime_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            current = Path(temporary) / "portable" / "UserData" / "data" / "saves" / "Save_Test"
            current.mkdir(parents=True)
            session = GameSession(None, "测试", save_dir_path=str(current))

            session.load_save_data({
                "save_name": "测试",
                "save_dir_path": r"C:\OldComputer\AliveWorld\data\saves\Save_Test",
            })

            self.assertEqual(Path(session.save_dir_path), current)

    def test_load_route_repairs_migrated_absolute_path_on_disk(self):
        with tempfile.TemporaryDirectory() as temporary:
            current = Path(temporary) / "UserData" / "data" / "saves" / "Save_Test"
            current.mkdir(parents=True)
            state_file = current / "session_state.json"
            save_data = {
                "save_name": "测试",
                "save_dir_path": r"D:\OldAliveWorld\data\saves\Save_Test",
                "_save_dir": str(current),
                "history": {"chat_messages": [], "context_history": [], "story_turns": []},
            }
            state_file.write_text(json.dumps(save_data, ensure_ascii=False), encoding="utf-8")

            with (
                patch.object(game_routes, "get_all_saves", return_value={"测试": save_data}),
                patch.object(game_routes, "global_ai_engine", None),
                patch.object(game_routes, "global_memory_ai_engine", None),
                patch.object(game_routes, "global_preference_ai_engine", None),
            ):
                game_routes.load_game(game_routes.LoadRequest(save_name="测试"))

            repaired = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(Path(repaired["save_dir_path"]), current)


if __name__ == "__main__":
    unittest.main()
