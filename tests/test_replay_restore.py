import tempfile
import unittest

from core.game_session import GameSession
from core.story_attempts import reference_context


class ReplayRestoreTests(unittest.TestCase):
    def test_reference_is_explicit_and_rejects_unknown_or_oversized_selection(self):
        attempts = [{"id": "a", "turns": [{"player": "old", "story": "result"}]}]
        self.assertEqual("", reference_context(attempts, []))
        self.assertIn("非正式参考", reference_context(attempts, ["a"]))
        with self.assertRaises(ValueError):
            reference_context(attempts, ["other-story"])
        attempts[0]["turns"][0]["story"] = "x" * 20001
        with self.assertRaises(ValueError):
            reference_context(attempts, ["a"])
    def test_attempts_survive_repeated_undo_and_reload_without_entering_history(self):
        with tempfile.TemporaryDirectory() as folder:
            game = GameSession(None, save_dir_path=folder)
            for number in (1, 2):
                game._take_snapshot()
                game.history["story_turns"].append({"turn_id": number, "player": "try", "story": str(number)})
            game.rollback(preserve_attempt=True)
            game.rollback(preserve_attempt=True)
            restored = GameSession(None, save_dir_path=folder)
            restored.load_save_data(game.export_save_data())
            self.assertEqual(2, len(restored.story_attempts))
            self.assertEqual([], restored.history["story_turns"])
            self.assertNotEqual(restored.story_attempts[0]["origin_id"], restored.story_attempts[1]["origin_id"])

    def test_transaction_failure_restores_archive_and_internal_rollback_does_not_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            game = GameSession(None, save_dir_path=folder)
            game._take_snapshot()
            game.history["story_turns"].append({"turn_id": 1, "player": "try", "story": "result"})
            checkpoint = game.capture_transaction_state()
            game.rollback(preserve_attempt=True)
            self.assertEqual(1, len(game.story_attempts))
            game.restore_transaction_state(checkpoint)
            self.assertEqual([], game.story_attempts)
            game.rollback()
            self.assertEqual([], game.story_attempts)

    def test_repeated_attempts_from_same_origin_share_identity_not_records(self):
        with tempfile.TemporaryDirectory() as folder:
            game = GameSession(None, save_dir_path=folder)
            for result in ("first", "second"):
                game._take_snapshot()
                game.history["story_turns"].append({"turn_id": 1, "player": "try", "story": result})
                game.rollback(preserve_attempt=True)
            first, second = game.story_attempts
            self.assertEqual(first["origin_id"], second["origin_id"])
            self.assertNotEqual(first["id"], second["id"])
            self.assertEqual("first", first["turns"][0]["story"])

    def test_undo_terminal_turn_restores_playable_state(self):
        with tempfile.TemporaryDirectory() as folder:
            game = GameSession(None, save_dir_path=folder)
            game._take_snapshot()
            game.is_game_over = True
            self.assertTrue(game.rollback())
            self.assertFalse(game.is_game_over)

    def test_terminal_state_survives_save_and_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            game = GameSession(None, save_dir_path=folder)
            game._take_snapshot()
            game.is_game_over = True
            restored = GameSession(None, save_dir_path=folder)
            restored.load_save_data(game.export_save_data())
            self.assertTrue(restored.is_game_over)
            self.assertTrue(restored.rollback())
            self.assertFalse(restored.is_game_over)

    def test_legacy_snapshot_is_playable_and_empty_undo_does_not_change_state(self):
        with tempfile.TemporaryDirectory() as folder:
            game = GameSession(None, save_dir_path=folder)
            game._take_snapshot()
            game.snapshots[-1].pop('is_game_over')
            game.is_game_over = True
            self.assertTrue(game.rollback())
            self.assertFalse(game.is_game_over)
            game.is_game_over = True
            self.assertFalse(game.rollback())
            self.assertTrue(game.is_game_over)

    def test_failed_mutation_can_restore_terminal_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            game = GameSession(None, save_dir_path=folder)
            game.is_game_over = True
            checkpoint = game.capture_transaction_state()
            game.is_game_over = False
            game.restore_transaction_state(checkpoint)
            self.assertTrue(game.is_game_over)
