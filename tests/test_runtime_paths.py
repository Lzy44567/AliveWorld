import tempfile
import unittest
from pathlib import Path

from utils.runtime_paths import prepare_runtime_layout, resolve_runtime_paths


class RuntimePathsTests(unittest.TestCase):
    def test_source_mode_preserves_repository_layout(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "AliveWorld"
            module = project / "utils" / "runtime_paths.py"
            paths = resolve_runtime_paths(environ={}, frozen=False, module_file=module)

            self.assertEqual(paths.resource_root, project.resolve())
            self.assertEqual(paths.user_root, project.resolve())
            self.assertEqual(paths.data_dir, (project / "data").resolve())
            self.assertFalse(paths.frozen)

    def test_frozen_mode_uses_local_appdata_for_private_user_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            resource = root / "bundle"
            local_appdata = root / "LocalAppData"
            paths = resolve_runtime_paths(
                environ={
                    "ALIVEWORLD_RESOURCE_DIR": str(resource),
                    "LOCALAPPDATA": str(local_appdata),
                },
                frozen=True,
                module_file=resource / "utils" / "runtime_paths.py",
            )

            self.assertEqual(paths.resource_root, resource.resolve())
            self.assertEqual(paths.user_root, (local_appdata / "AliveWorld").resolve())
            self.assertEqual(paths.config_file, (local_appdata / "AliveWorld" / "config.yml").resolve())
            self.assertTrue(paths.frozen)

    def test_prepare_layout_copies_only_templates_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            resource = root / "bundle"
            user = root / "user"
            (resource / "data" / "characters").mkdir(parents=True)
            (resource / "data" / "characters" / "hero.template.yml").write_text(
                "name: bundled\n", encoding="utf-8"
            )
            (resource / "data" / "characters" / "private.yml").write_text(
                "name: private\n", encoding="utf-8"
            )
            (resource / "config.example.yml").write_text("api_key: ''\n", encoding="utf-8")
            paths = resolve_runtime_paths(
                environ={
                    "ALIVEWORLD_RESOURCE_DIR": str(resource),
                    "ALIVEWORLD_USER_DIR": str(user),
                },
                frozen=True,
                module_file=resource / "utils" / "runtime_paths.py",
            )

            prepare_runtime_layout(paths)
            copied = user / "data" / "characters" / "hero.template.yml"
            self.assertEqual(copied.read_text(encoding="utf-8"), "name: bundled\n")
            self.assertFalse((user / "data" / "characters" / "private.yml").exists())
            self.assertTrue((user / "config.yml").is_file())

            copied.write_text("name: user-edited\n", encoding="utf-8")
            prepare_runtime_layout(paths)
            self.assertEqual(copied.read_text(encoding="utf-8"), "name: user-edited\n")


if __name__ == "__main__":
    unittest.main()
