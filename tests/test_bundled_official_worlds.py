import shutil
import tempfile
import unittest
from pathlib import Path

from core.entity_repository import EntityRepository
from core.world_packages.authoring import WorldPackageAuthoringService
from core.world_packages.service import WorldPackageService
from core.world_packages.starter_state import normalize_initial_state
from core.world_packages.models import PackageFormatError


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class BundledOfficialWorldTests(unittest.TestCase):
    def _copy_templates(self, target: Path) -> Path:
        data = target / "data"
        for folder in ("worldbooks", "characters", "styles", "entities", "world_packages"):
            source = PROJECT_ROOT / "data" / folder
            destination = data / folder
            destination.mkdir(parents=True, exist_ok=True)
            for path in source.glob("*.template.*"):
                shutil.copy2(path, destination / path.name)
        return data

    def test_large_official_world_exports_and_materializes_complete_story(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self._copy_templates(root)
            authoring = WorldPackageAuthoringService(data)
            catalog = authoring.official_catalog()
            self.assertEqual(catalog[0]["official_id"], "ash_ring_city")
            self.assertTrue(catalog[0]["featured"])
            self.assertEqual(catalog[0]["asset_count"], 9)

            archive, manifest = authoring.export_official("ash_ring_city")
            self.assertEqual(len(manifest["assets"]), 10)  # 9 story assets + starter
            self.assertEqual(len(manifest["entrypoints"]["characters"]), 3)
            self.assertEqual(len(manifest["entrypoints"]["entities"]), 4)

            service = WorldPackageService(data / "world_packages" / "installed", data)
            record = service.importer.install(archive)
            save = data / "saves" / "Save_烬环验收"
            save.mkdir(parents=True)
            starter = service.materialize_story(record.package_id, record.version, save)

            self.assertEqual(starter.initial_state["bars"]["下环供热"]["current"], 62)
            self.assertEqual(starter.initial_state["properties"]["当前时间"], "停炉前夜 21:50")
            self.assertTrue(starter.story_settings["entitiesEnabled"])
            self.assertTrue(starter.story_settings["showInfluenceBubbles"])
            self.assertFalse(starter.story_settings["worldbookCaptureEnabled"])
            self.assertEqual(len(EntityRepository(save).load()), 4)
            self.assertEqual(len(list((save / "characters").glob("*.yml"))), 3)
            self.assertTrue((save / "world_package.json").is_file())

    def test_initial_state_rejects_unknown_groups_and_unsafe_sizes(self):
        with self.assertRaisesRegex(PackageFormatError, "未知分组"):
            normalize_initial_state({"scripts": {"run": "anything"}})
        with self.assertRaisesRegex(PackageFormatError, "上限"):
            normalize_initial_state({"bars": {"错误": {"current": 1, "max": 0}}})


if __name__ == "__main__":
    unittest.main()
