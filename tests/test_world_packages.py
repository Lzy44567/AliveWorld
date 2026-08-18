import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import yaml

from core.asset_lifecycle import clone_yaml_asset
from core.world_packages import AssetSource, InstallLedger, PackageFormatError, WorldPackageExporter, WorldPackageImporter, WorldPackageService, new_package_id
from core.world_packages.models import new_asset_id
from core.world_packages.identity import asset_id_from_data, ensure_yaml_asset_id


class WorldPackageTests(unittest.TestCase):
    def _package(self, package_id: str) -> dict:
        return {
            "package_id": package_id,
            "version": "1.0.0",
            "name": "测试世界",
            "author": "测试作者",
            "description": "用于验证本地世界包",
            "tags": ("测试",),
        }

    def test_yaml_identity_is_stable_and_clone_gets_new_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "世界规则.yml"
            source.write_text("name: 世界规则\noverview: 测试\n", encoding="utf-8")
            first = ensure_yaml_asset_id(source)
            self.assertEqual(ensure_yaml_asset_id(source), first)
            clone = clone_yaml_asset(root, "世界规则", "世界规则分支", worldbook=True)
            clone_data = yaml.safe_load(clone.read_text(encoding="utf-8"))
            self.assertNotEqual(asset_id_from_data(clone_data), first)

    def test_export_install_round_trip_and_repeat_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "世界规则.yml"
            source.write_text("name: 世界规则\noverview: 测试\nentries: []\n", encoding="utf-8")
            archive = root / "测试世界.aliveworld"
            package_id = new_package_id()
            exported = WorldPackageExporter().export(
                archive,
                package=self._package(package_id),
                assets=[AssetSource("worldbooks", source)],
            )
            self.assertTrue(archive.is_file())
            self.assertEqual(exported.assets[0].asset_id, ensure_yaml_asset_id(source))
            with zipfile.ZipFile(archive, "r") as package_file:
                packaged = yaml.safe_load(package_file.read(exported.assets[0].path))
            self.assertEqual(asset_id_from_data(packaged), exported.assets[0].asset_id)
            importer = WorldPackageImporter(root / "UserData" / "data" / "world_packages")
            record = importer.install(archive)
            repeated = importer.install(archive)
            self.assertEqual(record, repeated)
            self.assertTrue((importer.root / record.manifest_path).is_file())
            self.assertEqual(len(InstallLedger(importer.root).list()), 1)

    def test_same_id_and_version_with_different_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "world.yml"
            source.write_text("name: 世界规则\noverview: 第一版\n", encoding="utf-8")
            package_id = new_package_id()
            first = root / "first.aliveworld"
            second = root / "second.aliveworld"
            exporter = WorldPackageExporter()
            exporter.export(first, package=self._package(package_id), assets=[AssetSource("worldbooks", source)])
            importer = WorldPackageImporter(root / "packages")
            importer.install(first)
            source.write_text(source.read_text(encoding="utf-8").replace("第一版", "不同内容"), encoding="utf-8")
            exporter.export(second, package=self._package(package_id), assets=[AssetSource("worldbooks", source)])
            with self.assertRaisesRegex(PackageFormatError, "拒绝静默替换"):
                importer.install(second)

    def test_export_rejects_private_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "world.yml"
            source.write_text("name: 世界规则\napi_key: sk-this-must-never-ship-123456\n", encoding="utf-8")
            with self.assertRaisesRegex(PackageFormatError, "隐私扫描未通过"):
                WorldPackageExporter().export(
                    root / "unsafe.aliveworld",
                    package=self._package(new_package_id()),
                    assets=[AssetSource("worldbooks", source)],
                )

    def test_import_rejects_tampered_asset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "world.yml"
            source.write_text("name: 世界规则\n", encoding="utf-8")
            archive = root / "world.aliveworld"
            WorldPackageExporter().export(
                archive,
                package=self._package(new_package_id()),
                assets=[AssetSource("worldbooks", source)],
            )
            with zipfile.ZipFile(archive, "r") as current:
                manifest = json.loads(current.read("manifest.json"))
            bad = root / "tampered.aliveworld"
            with zipfile.ZipFile(bad, "w") as output:
                output.writestr("manifest.json", json.dumps(manifest))
                output.writestr(manifest["assets"][0]["path"], b"changed")
            with self.assertRaisesRegex(PackageFormatError, "资产校验失败"):
                WorldPackageImporter(root / "packages").inspect(bad)

    def test_import_rejects_path_traversal_even_if_manifest_is_present(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "traversal.aliveworld"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("manifest.json", "{}")
                output.writestr("../escape.txt", "bad")
            with self.assertRaisesRegex(PackageFormatError, "不安全"):
                WorldPackageImporter(root / "packages").inspect(archive)

    def test_manifest_rejects_missing_dependency(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "world.yml"
            source.write_text("name: 世界规则\n", encoding="utf-8")
            with self.assertRaisesRegex(PackageFormatError, "不存在的依赖"):
                WorldPackageExporter().export(
                    root / "missing.aliveworld",
                    package=self._package(new_package_id()),
                    assets=[AssetSource("worldbooks", source, dependencies=("awasset_" + "0" * 32,))],
                )

    def test_materialize_story_uses_starter_and_copies_only_default_story_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "data"
            world = root / "world.yml"
            world.write_text("name: 世界规则\noverview: 包内世界\n", encoding="utf-8")
            world_id = ensure_yaml_asset_id(world)
            starter = root / "starter.json"
            starter.write_text(json.dumps({
                "world_premise": "包内梗概",
                "opening": "包内开场",
                "story_settings": {"aiSuggestions": False},
            }, ensure_ascii=False), encoding="utf-8")
            starter_id = new_asset_id()
            archive = root / "world.aliveworld"
            package = self._package(new_package_id())
            package["entrypoints"] = {"main_worldbook": world_id, "starter": starter_id}
            WorldPackageExporter().export(archive, package=package, assets=[
                AssetSource("worldbooks", world),
                AssetSource("starter", starter, name="默认起点", asset_id=starter_id),
            ])
            service = WorldPackageService(data / "world_packages", data)
            record = service.importer.install(archive)
            save = root / "Save_测试"
            save.mkdir()
            result = service.materialize_story(record.package_id, record.version, save)
            self.assertEqual(result.world_premise, "包内梗概")
            self.assertEqual(result.opening, "包内开场")
            self.assertFalse(result.story_settings["aiSuggestions"])
            self.assertEqual(len(list((save / "worldbooks").glob("*.yml"))), 1)
            self.assertTrue((save / "world_package.json").is_file())

    def test_safe_uninstall_preserves_modified_asset_and_removes_ledger_record(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "data"
            source = root / "world.yml"
            source.write_text("name: 世界规则\noverview: 原始\n", encoding="utf-8")
            archive = root / "world.aliveworld"
            package_id = new_package_id()
            WorldPackageExporter().export(archive, package=self._package(package_id), assets=[AssetSource("worldbooks", source)])
            service = WorldPackageService(data / "world_packages", data)
            record = service.importer.install(archive)
            story = root / "Save_继续保留"
            story.mkdir()
            service.materialize_story(package_id, "1.0.0", story)
            installed_asset = service.root / record.assets[0]["path"]
            installed_asset.write_text(installed_asset.read_text(encoding="utf-8").replace("原始", "玩家修改"), encoding="utf-8")
            result = service.uninstall(package_id, "1.0.0")
            self.assertEqual(result["status"], "removed")
            self.assertEqual(len(result["preserved_paths"]), 1)
            self.assertTrue(Path(result["preserved_paths"][0]).is_file())
            self.assertIsNone(service.importer.ledger.find(package_id, "1.0.0"))
            self.assertTrue(any((service.root / "uninstall_backups" / package_id).iterdir()))
            self.assertTrue((story / "world_package.json").is_file())
            self.assertEqual(len(list((story / "worldbooks").glob("*.yml"))), 1)


if __name__ == "__main__":
    unittest.main()
