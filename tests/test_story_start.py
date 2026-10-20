import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import yaml

from api.v1 import game_routes
from core.game_session import GameSession
from tests.test_game_action_suggestions import FakeResolver
from core.story_start_assets import prepare_start_assets, write_start_assets
from core.asset_lifecycle import AssetLifecycleError


class StoryStartTests(unittest.TestCase):
    def test_selected_assets_are_local_active_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.yml'
            original = 'name: 测试角色\nis_player: false\nis_active: false\ndescription: 喜欢探索\n'
            source.write_text(original, encoding='utf-8')
            with patch('core.story_start_assets.resolve_asset_path', return_value=source):
                prepared = prepare_start_assets({'characters': '测试角色'})
            (root / 'characters').mkdir()
            write_start_assets(str(root), prepared)
            local = yaml.safe_load((root / 'characters' / '测试角色.yml').read_text(encoding='utf-8'))
            self.assertTrue(local['is_player'])
            self.assertTrue(local['is_active'])
            self.assertEqual(source.read_text(encoding='utf-8'), original)

    def test_missing_asset_does_not_create_directory(self):
        with patch.object(game_routes, 'global_ai_engine', object()), patch('core.story_start_assets.resolve_asset_path', return_value=None), patch.object(game_routes, 'init_save_folder') as create:
            with self.assertRaises(game_routes.HTTPException) as error:
                game_routes.start_game(game_routes.StartRequest(save_name='test', worldbook='missing'))
            self.assertEqual(error.exception.status_code, 400)
            create.assert_not_called()

    def test_failed_creation_removes_only_new_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / 'old'
            old.mkdir()
            marker = old / 'keep.txt'
            marker.write_text('unchanged')
            new = root / 'new'
            new.mkdir()
            with patch.object(game_routes, 'global_ai_engine', object()), patch.object(game_routes, 'init_save_folder', return_value=str(new)), patch.object(game_routes, 'save_game_data', side_effect=OSError('disk full')), patch.object(game_routes, 'register_session') as register:
                with self.assertRaises(OSError):
                    game_routes.start_game(game_routes.StartRequest(save_name='test'))
                register.assert_not_called()
            self.assertFalse(new.exists())
            self.assertEqual(marker.read_text(), 'unchanged')

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
