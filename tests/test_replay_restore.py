import tempfile
import unittest

from core.game_session import GameSession


class ReplayRestoreTests(unittest.TestCase):
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
