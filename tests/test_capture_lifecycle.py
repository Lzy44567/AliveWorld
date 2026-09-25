import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

from api.v1.game_routes import _persisted_story_mutation
from api.v1.local_asset_routes import pull_asset, PullAssetRequest
from core.capture_source import source_is_current
from core.game_session import GameSession
from core.session_manager import mutation_guard, save_identity, register_session, unregister_session
from core.worldbook import save_worldbook_atomic, worldbook_revision, WorldbookRevisionConflict
from core.worldbook_capture import WorldbookCaptureService
from tests.test_game_action_suggestions import FakeResolver, RecordingAI
from tests.test_world_change_events import event
from utils.file_io import save_game_data


RESPONSE = json.dumps({"candidates": [{"name": "新规则", "content": "法令生效", "risk": "low",
                                      "scope": "social_system", "confidence": "high"}]})


class CaptureLifecycleTests(unittest.TestCase):
    def test_local_import_preserves_all_asset_types(self):
        with tempfile.TemporaryDirectory() as root:
            game = self.setup_story(root)
            register_session("capture-import-test", game)
            try:
                for category in ("worldbooks", "characters", "styles", "entities"):
                    source = Path(root) / "source.yml"
                    source.write_text(yaml.safe_dump({"name": "示例", "entries": [], "content": "原内容"}, allow_unicode=True), encoding="utf-8")
                    with patch("api.v1.local_asset_routes.resolve_asset_path", return_value=source):
                        response = pull_asset("capture-import-test", PullAssetRequest(asset_type=category, asset_name="示例"))
                    self.assertEqual(response["status"], "success")
                    self.assertEqual(yaml.safe_load((Path(root) / category / "示例.yml").read_text(encoding="utf-8"))["name"], "示例")
            finally:
                unregister_session("capture-import-test")

    def setup_story(self, root):
        session = GameSession(None, "test", str(root), {"worldbookCaptureEnabled": True})
        session.start_new_game("", "开场")
        payload = FakeResolver([]).resolve(session, "继续")
        payload["settlement"].update(story_text="法令今日生效。", world_change_events=[event()])
        session.resolver = Mock()
        session.resolver.resolve.return_value = payload
        session.worldbook_capture.schedule = Mock()
        return session

    def setup_files(self, root):
        path = Path(root) / "worldbooks" / "book.yml"
        save_worldbook_atomic(path, {"name": "世界", "entries": []})
        source = {"turn_id": 2, "player": "继续", "story": "法令今日生效。", "source_message_ids": ["unique-turn"]}
        save_game_data(root, {"history": {"story_turns": [source]}})
        return path, source

    def test_capture_only_dispatches_after_successful_save(self):
        with tempfile.TemporaryDirectory() as root:
            game = self.setup_story(root)
            def verify_source(_path, **task):
                self.assertTrue(source_is_current(root, task["source_turn"]))
            game.worldbook_capture.schedule.side_effect = verify_source
            _persisted_story_mutation(game, lambda: game.process_turn("继续"))
            game.worldbook_capture.schedule.assert_called_once()
            self.assertEqual(game._pending_worldbook_captures, [])

    def test_failed_save_discards_queue_and_does_not_schedule(self):
        with tempfile.TemporaryDirectory() as root:
            game = self.setup_story(root)
            before = copy.deepcopy(game.history)
            with patch("api.v1.game_routes.save_game_data", side_effect=OSError("full")):
                with self.assertRaises(OSError):
                    _persisted_story_mutation(game, lambda: game.process_turn("继续"))
            game.worldbook_capture.schedule.assert_not_called()
            self.assertEqual(game.history, before)
            self.assertEqual(game._pending_worldbook_captures, [])

    def test_reroll_dispatches_new_source_only_after_commit(self):
        with tempfile.TemporaryDirectory() as root:
            game = self.setup_story(root)
            game.story_settings["entitiesEnabled"] = False
            _persisted_story_mutation(game, lambda: game.process_turn("继续"))
            old_source = copy.deepcopy(game.history["story_turns"][-1])
            game.worldbook_capture.schedule.reset_mock()
            game.ai_engine = RecordingAI(json.dumps({"story_text": "法令今日生效。", "world_change_events": [event()]}))
            result = _persisted_story_mutation(game, game.reroll_turn)
            self.assertFalse(result.get("error"))
            game.worldbook_capture.schedule.assert_called_once()
            new_source = game.worldbook_capture.schedule.call_args.kwargs["source_turn"]
            self.assertTrue(source_is_current(root, new_source))
            self.assertFalse(source_is_current(root, old_source))

    def test_current_source_commits_and_survives_reload(self):
        with tempfile.TemporaryDirectory() as root:
            path, source = self.setup_files(root)
            ai = Mock()
            ai.chat_json.return_value = (RESPONSE, None)
            result = WorldbookCaptureService(ai).capture(path, "继续", source["story"], review_all=False,
                source_turn=source, save_dir=root)
            self.assertEqual(len(result["added"]), 1)
            self.assertEqual(yaml.safe_load(path.read_text(encoding="utf-8"))["entries"][0]["name"], "新规则")

    def test_unsaved_source_never_starts_worker(self):
        with tempfile.TemporaryDirectory() as root:
            path, source = self.setup_files(root)
            (Path(root) / "session_state.json").unlink()
            with patch("core.worldbook_capture.threading.Thread") as thread:
                self.assertFalse(WorldbookCaptureService(Mock()).schedule(root, "继续", source["story"],
                    review_all=True, source_turn=source))
            thread.assert_not_called()

    def test_failed_worldbook_write_preserves_original_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as root:
            path, source = self.setup_files(root)
            original = path.read_bytes()
            ai = Mock()
            ai.chat_json.return_value = (RESPONSE, None)
            with patch("core.worldbook.os.replace", side_effect=OSError("disk full")):
                result = WorldbookCaptureService(ai).capture(path, "继续", source["story"], review_all=False,
                    source_turn=source, save_dir=root)
            self.assertEqual(result["added"], [])
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_dispatch_failure_does_not_roll_back_committed_story(self):
        with tempfile.TemporaryDirectory() as root:
            game = self.setup_story(root)
            game.worldbook_capture.schedule.side_effect = RuntimeError("thread unavailable")
            _persisted_story_mutation(game, lambda: game.process_turn("继续"))
            self.assertTrue(source_is_current(root, game.history["story_turns"][-1]))

    def test_reused_turn_number_with_different_identity_is_stale(self):
        with tempfile.TemporaryDirectory() as root:
            _, source = self.setup_files(root)
            replacement = {**source, "source_message_ids": ["another-turn"]}
            save_game_data(root, {"history": {"story_turns": [replacement]}})
            self.assertFalse(source_is_current(root, source))

    def run_blocked_capture(self, root, mutate):
        path, source = self.setup_files(root)
        entered, release = threading.Event(), threading.Event()
        ai = Mock()
        def respond(*args, **kwargs):
            entered.set()
            if not release.wait(3):
                raise AssertionError("test did not release provider")
            return RESPONSE, None
        ai.chat_json.side_effect = respond
        service = WorldbookCaptureService(ai)
        results = []
        worker = threading.Thread(target=lambda: results.append(service.capture(
            path, "继续", source["story"], review_all=False, source_turn=source, save_dir=root)))
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            mutate(path, source)
        finally:
            release.set()
            worker.join(4)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results[0]["added"], [])
        self.assertTrue(results[0]["skipped"])
        return path

    def test_undo_during_model_call_discards_result(self):
        with tempfile.TemporaryDirectory() as root:
            def undo(path, source):
                with mutation_guard("story", save_identity(root)):
                    save_game_data(root, {"history": {"story_turns": []}})
            path = self.run_blocked_capture(root, undo)
            self.assertEqual(yaml.safe_load(path.read_text(encoding="utf-8"))["entries"], [])

    def test_target_edit_during_model_call_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.run_blocked_capture(root, lambda path, source: save_worldbook_atomic(path, {"name": "手动修改", "entries": []}))
            self.assertEqual(yaml.safe_load(path.read_text(encoding="utf-8"))["name"], "手动修改")

    def test_deleted_target_is_not_recreated(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.run_blocked_capture(root, lambda path, source: path.unlink())
            self.assertFalse(path.exists())

    def test_revision_already_changed_before_worker_makes_zero_calls(self):
        with tempfile.TemporaryDirectory() as root:
            path, source = self.setup_files(root)
            revision = worldbook_revision(path.read_bytes())
            save_worldbook_atomic(path, {"name": "新版", "entries": []})
            ai = Mock()
            result = WorldbookCaptureService(ai).capture(path, "继续", source["story"], review_all=False,
                source_turn=source, save_dir=root, expected_revision=revision)
            ai.chat_json.assert_not_called()
            self.assertTrue(result["skipped"])

    def test_atomic_writer_rejects_stale_revision(self):
        with tempfile.TemporaryDirectory() as root:
            path, _ = self.setup_files(root)
            before = path.read_bytes()
            with self.assertRaises(WorldbookRevisionConflict):
                save_worldbook_atomic(path, {"name": "覆盖"}, expected_revision="wrong")
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
