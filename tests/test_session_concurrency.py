import tempfile
import threading
import unittest
import copy
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from api.v1.game_routes import ActionRequest, process_turn

from core.session_manager import (
    MutationBusyError, existing_session, mutation_guard, register_session,
    unregister_session,
)


class _Game:
    def __init__(self, path):
        self.save_dir_path = str(path)


class _SlowGame(_Game):
    def __init__(self, path, entered, release):
        super().__init__(path)
        self.entered = entered
        self.release = release
        self.history = {"chat_messages": []}
        self.state = {}
        self.is_game_over = False
        self.action_suggestions = []
        self.plot_compass = ""

    def process_turn(self, _action):
        self.entered.set()
        self.release.wait(2)
        return {"error": False}

    def export_save_data(self):
        return {}

    def capture_transaction_state(self):
        return {"history": list(self.history["chat_messages"])}

    def restore_transaction_state(self, snapshot):
        self.history["chat_messages"] = list(snapshot["history"])


class _TransactionalGame(_SlowGame):
    def __init__(self, path):
        super().__init__(path, threading.Event(), threading.Event())
        self.release.set()
        self.state = {"properties": {"阶段": "保存前"}}

    def process_turn(self, action):
        self.history["chat_messages"].append({"role": "user", "content": action})
        self.state["properties"]["阶段"] = "尚未落盘"
        return {"error": False}

    def capture_transaction_state(self):
        return {"history": copy.deepcopy(self.history), "state": copy.deepcopy(self.state)}

    def restore_transaction_state(self, snapshot):
        self.history = copy.deepcopy(snapshot["history"])
        self.state = copy.deepcopy(snapshot["state"])


class SessionConcurrencyTests(unittest.TestCase):
    def test_same_key_is_rejected_while_different_key_can_enter(self):
        entered = threading.Event()
        release = threading.Event()

        def hold():
            with mutation_guard("story", "save-a"):
                entered.set()
                release.wait(2)

        worker = threading.Thread(target=hold)
        worker.start()
        self.assertTrue(entered.wait(1))
        with self.assertRaises(MutationBusyError):
            with mutation_guard("story", "save-a"):
                pass
        with mutation_guard("story", "save-b"):
            pass
        release.set()
        worker.join(2)
        self.assertFalse(worker.is_alive())
        with mutation_guard("story", "save-a"):
            pass

    def test_loading_same_save_reuses_registered_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "Save_A"
            path.mkdir()
            game = _Game(path)
            register_session("session-a", game)
            try:
                found = existing_session(str(path / ".." / "Save_A"))
                self.assertEqual(found, ("session-a", game))
            finally:
                unregister_session("session-a")
            self.assertIsNone(existing_session(str(path)))

    def test_story_route_maps_same_save_overlap_to_conflict(self):
        with tempfile.TemporaryDirectory() as temporary:
            entered, release = threading.Event(), threading.Event()
            game = _SlowGame(Path(temporary), entered, release)
            register_session("slow-session", game)
            outcomes = []

            def first():
                with patch("api.v1.game_routes.save_game_data"):
                    outcomes.append(process_turn("slow-session", ActionRequest(action="first")))

            worker = threading.Thread(target=first)
            worker.start()
            self.assertTrue(entered.wait(1))
            try:
                with patch("api.v1.game_routes.save_game_data"):
                    with self.assertRaises(HTTPException) as raised:
                        process_turn("slow-session", ActionRequest(action="second"))
                self.assertEqual(raised.exception.status_code, 409)
            finally:
                release.set()
                worker.join(2)
                unregister_session("slow-session")
            self.assertEqual(len(outcomes), 1)

    def test_save_failure_restores_in_memory_story_transaction(self):
        with tempfile.TemporaryDirectory() as temporary:
            game = _TransactionalGame(Path(temporary))
            register_session("transaction-session", game)
            try:
                with patch("api.v1.game_routes.save_game_data", side_effect=OSError("disk full")):
                    with self.assertRaisesRegex(OSError, "disk full"):
                        process_turn("transaction-session", ActionRequest(action="advance"))
                self.assertEqual(game.history["chat_messages"], [])
                self.assertEqual(game.state["properties"]["阶段"], "保存前")
            finally:
                unregister_session("transaction-session")


if __name__ == "__main__":
    unittest.main()
