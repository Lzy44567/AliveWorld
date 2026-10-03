import copy
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.character_chat.models import (CharacterSessionError, create_session,
                                        profile_projection)
from core.character_chat.repository import CharacterSessionRepository


class CharacterStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = CharacterSessionRepository(self.root / "character_sessions")
        self.creation = str(uuid4())
        self.profile = {"name": "测试角色", "description": "有自己的立场",
                        "is_player": True, "_external_import": {"source": {"unknown": "保留"}}}
        self.value = create_session(self.creation, self.profile,
                                    {"kind": "character", "key": "测试角色.yml"})
        self.sid = self.value["session_id"]

    def assert_code(self, code, call):
        with self.assertRaises(CharacterSessionError) as caught:
            call()
        self.assertEqual(code, caught.exception.code)

    def test_creation_snapshot_and_projection(self):
        self.profile["description"] = "原卡后来改变"
        saved = self.repo.create(self.value)
        ai = saved["participants"][1]
        self.assertEqual("有自己的立场", ai["profile_snapshot"]["description"])
        self.assertEqual("ai", ai["controller"])
        self.assertEqual({"name", "description", "starting_scene"}, set(profile_projection(ai)))
        self.assertIn("_external_import", ai["profile_snapshot"])
        saved["title"] = "改动返回值"
        self.assertEqual("测试角色", self.repo.load(self.sid)["title"])

    def test_recreate_same_intent_does_not_reset_current_state(self):
        self.repo.create(self.value)
        changed = copy.deepcopy(self.value)
        changed.update(title="新会话标题", revision=1)
        self.repo.save(changed, expected_revision=0)
        recreated = create_session(self.creation, self.profile, {"kind": "character", "key": "测试角色.yml"})
        self.assertEqual("新会话标题", self.repo.create(recreated)["title"])
        self.assertEqual(1, self.repo.load(self.sid)["revision"])

    def test_same_creation_different_profile_conflicts(self):
        self.repo.create(self.value)
        other = create_session(self.creation, {"name": "另一人", "description": "另一描述"},
                               {"kind": "character", "key": "其他.yml"})
        self.assert_code("IDEMPOTENCY_MISMATCH", lambda: self.repo.create(other))

    def test_freeze_card_and_bindings(self):
        self.repo.create(self.value)
        changed = copy.deepcopy(self.value)
        changed["revision"] = 1
        changed["participants"][1]["profile_snapshot"]["description"] = "擅自改变人格"
        self.assert_code("PROFILE_FROZEN", lambda: self.repo.save(changed, expected_revision=0))
        self.assertEqual(0, self.repo.load(self.sid)["revision"])

    def test_concurrent_revision_only_one_writer_wins(self):
        self.repo.create(self.value)
        def write(title):
            changed = copy.deepcopy(self.value)
            changed.update(title=title, revision=1)
            try:
                self.repo.save(changed, expected_revision=0)
                return "saved"
            except CharacterSessionError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, ["一", "二"]))
        self.assertCountEqual(["saved", "REVISION_CONFLICT"], results)

    def test_atomic_replace_failure_keeps_original_and_removes_temporary(self):
        self.repo.create(self.value)
        path = self.repo.directory / f"{self.sid}.json"
        original = path.read_bytes()
        changed = copy.deepcopy(self.value)
        changed.update(title="不能保存", revision=1)
        with patch("core.character_chat.repository.os.replace", side_effect=OSError("private path")):
            self.assert_code("PERSISTENCE_FAILED", lambda: self.repo.save(changed, expected_revision=0))
        self.assertEqual(original, path.read_bytes())
        self.assertEqual([], list(self.repo.directory.glob("*.tmp")))

    def test_delete_clears_contents_and_blocks_creation_replay(self):
        self.repo.create(self.value)
        self.repo.delete(self.sid, expected_revision=0)
        self.repo.delete(self.sid, expected_revision=0)
        raw = json.loads((self.repo.directory / f"{self.sid}.json").read_text(encoding="utf-8"))
        self.assertEqual({"schema_version", "session_id", "deleted"}, set(raw))
        self.assert_code("SESSION_DELETED", lambda: self.repo.create(self.value))
        self.assert_code("SESSION_DELETED", lambda: self.repo.load(self.sid))

    def test_unknown_schema_can_be_inspected_but_not_overwritten(self):
        self.repo.create(self.value)
        path = self.repo.directory / f"{self.sid}.json"
        future = copy.deepcopy(self.value)
        future.update(schema_version=2, future_field="保留")
        path.write_text(json.dumps(future), encoding="utf-8")
        original = path.read_bytes()
        self.assertEqual("保留", self.repo.load(self.sid)["future_field"])
        changed = copy.deepcopy(self.value)
        changed["revision"] = 1
        self.assert_code("SCHEMA_READ_ONLY", lambda: self.repo.save(changed, expected_revision=0))
        self.assert_code("SCHEMA_READ_ONLY", lambda: self.repo.delete(self.sid, expected_revision=0))
        self.assertEqual(original, path.read_bytes())

    def test_corrupt_duplicate_json_is_not_treated_as_empty(self):
        self.repo.create(self.value)
        path = self.repo.directory / f"{self.sid}.json"
        raw = ('{"session_id":"' + self.sid + '","revision":0,"revision":1}')
        path.write_text(raw, encoding="utf-8")
        self.assert_code("SESSION_CORRUPT", lambda: self.repo.create(self.value))
        self.assertEqual(raw, path.read_text(encoding="utf-8"))

    def test_paths_and_bad_inputs_rejected(self):
        for identifier in ("../secret", "", None, self.sid.upper()):
            self.assert_code("INVALID_REQUEST", lambda: self.repo.load(identifier))
        self.assert_code("INVALID_REQUEST", lambda: create_session(self.creation,
                         {"name": "空人设", "description": ""}, {"kind": "character", "key": "x"}))
        self.assert_code("INPUT_LIMIT", lambda: create_session(self.creation,
                         {"name": "人", "description": "x" * 32001}, {"kind": "character", "key": "x"}))

    def test_two_sessions_and_source_files_remain_independent(self):
        source = self.root / "角色.yml"
        source.write_bytes(b"untouched source")
        self.repo.create(self.value)
        other = create_session(str(uuid4()), self.profile, {"kind": "character", "key": "测试角色.yml"},
                               presentation_mode="roleplay")
        self.repo.create(other)
        self.repo.delete(self.sid, expected_revision=0)
        self.assertEqual("roleplay", self.repo.load(other["session_id"])["presentation_mode"])
        self.assertEqual(b"untouched source", source.read_bytes())


if __name__ == "__main__":
    unittest.main()
