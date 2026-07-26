import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from api.v1 import lobby_routes


class LegacyMigrationRouteTests(unittest.TestCase):
    def test_status_prompts_until_success_marker_exists(self):
        with tempfile.TemporaryDirectory() as temporary:
            user_root = Path(temporary) / "UserData"
            user_root.mkdir()
            legacy_root = Path(temporary) / "OldAliveWorld"
            paths = SimpleNamespace(
                user_root=user_root,
                resource_root=Path(temporary) / "bundle",
            )
            with (
                patch.object(lobby_routes, "PATHS", paths),
                patch.object(lobby_routes, "discover_legacy_root", return_value=legacy_root),
            ):
                pending = asyncio.run(lobby_routes.legacy_migration_status())
                (user_root / "legacy_migration.json").write_text("{}", encoding="utf-8")
                completed = asyncio.run(lobby_routes.legacy_migration_status())

        self.assertTrue(pending["should_prompt"])
        self.assertEqual(pending["source_root"], str(legacy_root))
        self.assertFalse(completed["should_prompt"])
        self.assertTrue(completed["completed"])


if __name__ == "__main__":
    unittest.main()
