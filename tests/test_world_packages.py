import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import yaml

from core.asset_lifecycle import clone_yaml_asset
from core.world_packages import AssetSource, InstallLedger, PackageFormatError, WorldPackageExporter, WorldPackageImporter, new_package_id
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


if __name__ == "__main__":
    unittest.main()
