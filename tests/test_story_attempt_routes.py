import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from api.v1.game_routes import list_story_attempts, delete_story_attempt
from core.game_session import GameSession
from core.session_manager import register_session, unregister_session, mutation_guard, save_identity


class StoryAttemptRoutesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.game = GameSession(None, save_dir_path=self.temp.name)
        self.game._take_snapshot()
        self.game.history['story_turns'].append({'turn_id': 1, 'player': '探路', 'story': '旧结果'})
        self.game.rollback(preserve_attempt=True)
        register_session('attempt-test', self.game)

    def tearDown(self):
        unregister_session('attempt-test')
        self.temp.cleanup()

    def test_list_is_detached_and_delete_persists_without_changing_story(self):
        result = list_story_attempts('attempt-test')
        attempt_id = result['attempts'][0]['id']
        result['attempts'].clear()
        self.assertEqual(1, len(self.game.story_attempts))
        history = copy.deepcopy(self.game.history)
        delete_story_attempt('attempt-test', attempt_id)
        saved = json.loads((Path(self.temp.name) / 'session_state.json').read_text(encoding='utf-8'))
        self.assertEqual([], saved['story_attempts'])
        self.assertEqual(history, self.game.history)

    def test_delete_failure_restores_archive(self):
        original = copy.deepcopy(self.game.story_attempts)
        with patch('api.v1.game_routes.save_game_data', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):
                delete_story_attempt('attempt-test', original[0]['id'])
        self.assertEqual(original, self.game.story_attempts)

    def test_busy_and_unknown_ids_do_not_modify_archive(self):
        with mutation_guard('story', save_identity(self.temp.name)):
            with self.assertRaises(HTTPException) as error:
                list_story_attempts('attempt-test')
            self.assertEqual(409, error.exception.status_code)
        with self.assertRaises(HTTPException) as error:
            delete_story_attempt('attempt-test', 'not-in-this-story')
        self.assertEqual(404, error.exception.status_code)
        self.assertEqual(1, len(self.game.story_attempts))
