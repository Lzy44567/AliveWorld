import tempfile
import unittest
from unittest.mock import patch

from api.v1 import game_routes
from core.game_session import GameSession
from tests.test_game_action_suggestions import FakeResolver


class StoryStartTests(unittest.TestCase):
    def test_blank_start_first_turn_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            game = GameSession(None, 'test', directory)
            game.start_new_game('山间驿站', '  \n ')
            self.assertEqual(game.history, {'chat_messages': [], 'context_history': [], 'story_turns': []})
            game.resolver = FakeResolver([])
            game.process_turn('观察广场')
            self.assertEqual([m['role'] for m in game.history['chat_messages'] if m['role'] in ('user', 'ai')], ['user', 'ai'])
            self.assertNotIn('时间线已建立', game.get_context_text())
            game.rollback()
            self.assertEqual(game.history['chat_messages'], [])

    def test_opening_survives_save_load_without_tutorial(self):
        with tempfile.TemporaryDirectory() as directory:
            game = GameSession(None, 'test', directory)
            game.start_new_game('山间驿站', '  门外下着雨。  ')
            loaded = GameSession(None, 'test', directory)
            loaded.load_save_data(game.export_save_data(), save_dir_path=directory)
            self.assertEqual(loaded.history['context_history'], ['门外下着雨。'])
            self.assertEqual(loaded.history['story_turns'][0]['turn_id'], 0)
            self.assertEqual(loaded.history['chat_messages'][0]['content'], '门外下着雨。')

    def test_request_forwards_optional_opening_and_legacy_description(self):
        with patch.object(game_routes, 'global_ai_engine', object()), patch.object(game_routes, 'init_save_folder', return_value='isolated'), patch.object(game_routes, 'start_prepared_game', return_value={}) as prepared:
            game_routes.start_game(game_routes.StartRequest(save_name='test', description='legacy', opening='门外下雨'))
            self.assertEqual(prepared.call_args.kwargs['opening'], '门外下雨')
            self.assertEqual(prepared.call_args.kwargs['world_premise'], 'legacy')
            game_routes.start_game(game_routes.StartRequest(save_name='test'))
            self.assertEqual(prepared.call_args.kwargs['opening'], '')

    def test_prepared_blank_start_does_not_invent_story(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(game_routes, 'global_ai_engine', object()), patch.object(game_routes, 'register_session'), patch.object(game_routes, 'save_game_data'):
            result = game_routes.start_prepared_game(save_name='test', save_dir_path=directory, world_premise='山间驿站')
            self.assertEqual(result['chat_messages'], [])


if __name__ == '__main__':
    unittest.main()
