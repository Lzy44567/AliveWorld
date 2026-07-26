import tempfile
import unittest
from pathlib import Path

import yaml

from utils.legacy_migration import (
    discover_legacy_root,
    migrate_legacy_data,
)
from utils.runtime_paths import resolve_runtime_paths


class LegacyMigrationTests(unittest.TestCase):
    def test_discovers_ancestor_source_with_personal_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "AliveWorld"
            executable = root / "release" / "portable" / "AliveWorld.exe"
            save = root / "data" / "saves" / "Save_Test" / "session_state.json"
            save.parent.mkdir(parents=True)
            save.write_text("{}", encoding="utf-8")

            discovered = discover_legacy_root(executable=executable, environ={})
            self.assertEqual(discovered, root.resolve())

    def test_does_not_scan_unrelated_user_data_locations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = root / "UnrelatedUserData" / "AliveWorld"
            save = legacy / "data" / "saves" / "Save_Test" / "session_state.json"
            save.parent.mkdir(parents=True)
            save.write_text("{}", encoding="utf-8")

            discovered = discover_legacy_root(
                executable=root / "portable" / "AliveWorld.exe",
                environ={"LOCALAPPDATA": str(root / "UnrelatedUserData")},
            )
            self.assertIsNone(discovered)

    def test_copies_personal_data_without_overwriting_or_copying_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "legacy"
            resource = root / "bundle"
            user = root / "user"
            (resource / "config.example.yml").parent.mkdir(parents=True)
            (resource / "config.example.yml").write_text("api_key: ''\n", encoding="utf-8")
            paths = resolve_runtime_paths(
                environ={
                    "ALIVEWORLD_RESOURCE_DIR": str(resource),
                    "ALIVEWORLD_USER_DIR": str(user),
                },
                frozen=True,
                module_file=resource / "utils" / "runtime_paths.py",
            )
            paths.data_dir.mkdir(parents=True)
            paths.config_file.write_text("api_key: ''\n", encoding="utf-8")

            legacy_save = source / "data" / "saves" / "Save_One" / "session_state.json"
            legacy_save.parent.mkdir(parents=True)
            legacy_save.write_text('{"old": true}', encoding="utf-8")
            legacy_character = source / "data" / "characters" / "hero.yml"
            legacy_character.parent.mkdir(parents=True)
            legacy_character.write_text("name: old\n", encoding="utf-8")
            cached = source / "data" / "cache" / "large.bin"
            cached.parent.mkdir(parents=True)
            cached.write_bytes(b"cache")
            (source / "config.yml").write_text("api_key: secret\n", encoding="utf-8")

            existing = paths.data_dir / "characters" / "hero.yml"
            existing.parent.mkdir(parents=True)
            existing.write_text("name: new\n", encoding="utf-8")

            report = migrate_legacy_data(source, paths)

            self.assertTrue((paths.data_dir / "saves" / "Save_One" / "session_state.json").is_file())
            self.assertEqual(existing.read_text(encoding="utf-8"), "name: new\n")
            self.assertFalse((paths.data_dir / "cache" / "large.bin").exists())
            self.assertEqual(paths.config_file.read_text(encoding="utf-8"), "api_key: secret\n")
            self.assertEqual(report.copied_files, 1)
            self.assertEqual(report.skipped_conflicts, 1)
            self.assertTrue(report.copied_config)

    def test_reformatted_but_unconfigured_target_accepts_legacy_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "legacy"
            resource = root / "bundle"
            user = root / "user"
            resource.mkdir()
            user.mkdir()
            (resource / "config.example.yml").write_text("api_key: ''\n", encoding="utf-8")
            (source / "config.yml").parent.mkdir(parents=True)
            (source / "config.yml").write_text(
                "api_key: inherited-secret\nmodel: inherited-model\n",
                encoding="utf-8",
            )
            paths = resolve_runtime_paths(
                environ={
                    "ALIVEWORLD_RESOURCE_DIR": str(resource),
                    "ALIVEWORLD_USER_DIR": str(user),
                },
                frozen=True,
                module_file=resource / "utils" / "runtime_paths.py",
            )
            paths.config_file.write_text(
                "api_key: ''\nmodel: reformatted-default\nmemory_context_limit: 32768\n",
                encoding="utf-8",
            )

            report = migrate_legacy_data(source, paths)

            self.assertTrue(report.copied_config)
            self.assertIn("inherited-model", paths.config_file.read_text(encoding="utf-8"))

    def test_configured_target_secret_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "legacy"
            resource = root / "bundle"
            user = root / "user"
            resource.mkdir()
            user.mkdir()
            (resource / "config.example.yml").write_text("api_key: ''\n", encoding="utf-8")
            (source / "config.yml").parent.mkdir(parents=True)
            (source / "config.yml").write_text("api_key: old-secret\n", encoding="utf-8")
            paths = resolve_runtime_paths(
                environ={
                    "ALIVEWORLD_RESOURCE_DIR": str(resource),
                    "ALIVEWORLD_USER_DIR": str(user),
                },
                frozen=True,
                module_file=resource / "utils" / "runtime_paths.py",
            )
            paths.config_file.write_text("api_key: new-secret\n", encoding="utf-8")

            report = migrate_legacy_data(source, paths)

            self.assertFalse(report.copied_config)
            self.assertEqual(
                yaml.safe_load(paths.config_file.read_text(encoding="utf-8"))["api_key"],
                "new-secret",
            )


if __name__ == "__main__":
    unittest.main()
