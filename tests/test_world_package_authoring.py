import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.world_packages.authoring import AssetSelection, WorldPackageAuthoringService
from core.world_packages.models import PackageFormatError
from core.world_packages.service import WorldPackageService
from main import create_app


class WorldPackageAuthoringTests(unittest.TestCase):
    def _service(self, root: Path) -> WorldPackageAuthoringService:
        data = root / "data"
        for folder in ("worldbooks", "characters", "styles", "entities"):
            (data / folder).mkdir(parents=True, exist_ok=True)
        (data / "worldbooks" / "demo.yml").write_text(
            "name: 测试世界书\noverview: 只打包明确选择的设定\nentries: []\n",
            encoding="utf-8",
        )
        (data / "characters" / "hero.yml").write_text(
            "name: 测试角色\ndescription: 保留玩家行动权的向导\n",
            encoding="utf-8",
        )
        return WorldPackageAuthoringService(data)

    def _payload(self) -> dict:
        return {
            "version": "1.0.0",
            "name": "工坊测试包",
            "author": "自动验收",
            "description": "验证工坊选择和本地导出",
            "tags": ["测试"],
        }

    def _add_official_definition(self, root: Path) -> None:
        data = root / "data"
        (data / "worldbooks" / "official.template.yml").write_text(
            "name: 官方测试世界\noverview: 官方模板必须优先于同名个人资产\nis_template: true\n",
            encoding="utf-8",
        )
        (data / "world_packages").mkdir(parents=True, exist_ok=True)
        (data / "world_packages" / "official_demo.template.json").write_text(json.dumps({
            "official_id": "official_demo",
            "metadata": {
                "package_id": "awpkg_" + "1" * 32,
                "version": "1.0.0",
                "name": "官方测试世界",
                "author": "自动验收",
            },
            "assets": [{"type": "worldbooks", "name": "官方测试世界"}],
            "starter": {
                "world_premise": "官方梗概", "opening": "官方开场", "story_settings": {},
                "initial_state": {
                    "properties": {"当前时间": "测试纪元"},
                    "bars": {"世界活性": {"current": 60, "max": 100, "color": "cyan"}},
                },
            },
        }, ensure_ascii=False), encoding="utf-8")

    def test_catalog_and_export_only_selected_assets_with_starter(self):
        with tempfile.TemporaryDirectory() as temp:
            service = self._service(Path(temp))
            self.assertEqual({item["name"] for item in service.catalog()}, {"测试世界书", "测试角色"})
            target, manifest = service.export(
                metadata=self._payload(),
                selections=[AssetSelection("worldbooks", "测试世界书")],
                starter={"world_premise": "测试梗概", "opening": "测试开场", "story_settings": {}},
            )
            self.assertTrue(target.is_file())
            self.assertEqual([item["type"] for item in manifest["assets"]], ["worldbooks", "starter"])
            with zipfile.ZipFile(target) as archive:
                starter_id = manifest["entrypoints"]["starter"]
                starter_record = next(item for item in manifest["assets"] if item["asset_id"] == starter_id)
                starter = json.loads(archive.read(starter_record["path"]))
            self.assertEqual(starter["opening"], "测试开场")
            self.assertEqual(manifest["entrypoints"]["main_worldbook"], manifest["assets"][0]["asset_id"])

    def test_export_rejects_empty_or_unknown_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            service = self._service(Path(temp))
            with self.assertRaisesRegex(PackageFormatError, "至少选择"):
                service.export(metadata=self._payload(), selections=[])
            with self.assertRaisesRegex(PackageFormatError, "找不到"):
                service.export(
                    metadata=self._payload(),
                    selections=[AssetSelection("worldbooks", "不存在")],
                )

    def test_repeat_export_is_deterministic_and_version_cannot_escape_export_dir(self):
        with tempfile.TemporaryDirectory() as temp:
            service = self._service(Path(temp))
            metadata = {**self._payload(), "package_id": "awpkg_" + "2" * 32}
            selection = [AssetSelection("worldbooks", "测试世界书")]
            first, _ = service.export(metadata=metadata, selections=selection)
            first_bytes = first.read_bytes()
            second, _ = service.export(metadata=metadata, selections=selection)
            self.assertEqual(first_bytes, second.read_bytes())
            with self.assertRaisesRegex(PackageFormatError, "版本格式"):
                service.export(metadata={**metadata, "version": "../escape"}, selections=selection)
            self.assertFalse((service.export_root.parent / "escape.aliveworld").exists())

    def test_official_definition_builds_a_normal_portable_package(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            service = self._service(root)
            self._add_official_definition(root)
            catalog = service.official_catalog()
            self.assertEqual([item["official_id"] for item in catalog], ["official_demo"])
            target, manifest = service.export_official("official_demo")
            self.assertTrue(target.is_file())
            self.assertEqual(manifest["package_id"], "awpkg_" + "1" * 32)
            self.assertEqual(manifest["name"], "官方测试世界")

    def test_official_starter_preserves_validated_initial_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            authoring = self._service(root)
            self._add_official_definition(root)
            target, manifest = authoring.export_official("official_demo")
            package_service = WorldPackageService(root / "installed", root / "data")
            record = package_service.importer.install(target)
            save = root / "save"
            save.mkdir()
            starter = package_service.materialize_story(record.package_id, record.version, save)
            self.assertEqual(starter.initial_state["properties"]["当前时间"], "测试纪元")
            self.assertEqual(starter.initial_state["bars"]["世界活性"]["current"], 60)
            self.assertEqual(starter.initial_state["bars"]["世界活性"]["change"], 0)

    def test_starter_settings_extend_instead_of_erasing_experience_preset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            service = self._service(root)
            self._add_official_definition(root)
            definition_path = root / "data" / "world_packages" / "official_demo.template.json"
            definition = json.loads(definition_path.read_text(encoding="utf-8"))
            definition["metadata"]["experience_preset"] = {
                "defaults": {"entitiesEnabled": True, "worldbookCaptureEnabled": False},
                "visibility": {"showEntityBubbles": True},
                "required_capabilities": [], "locked_keys": [],
            }
            definition["starter"]["story_settings"] = {"showEntityBubbles": False}
            definition_path.write_text(json.dumps(definition, ensure_ascii=False), encoding="utf-8")
            target, _ = service.export_official("official_demo")
            package_service = WorldPackageService(root / "installed", root / "data")
            record = package_service.importer.install(target)
            save = root / "save"
            save.mkdir()
            starter = package_service.materialize_story(record.package_id, record.version, save)
            self.assertTrue(starter.story_settings["entitiesEnabled"])
            self.assertFalse(starter.story_settings["worldbookCaptureEnabled"])
            self.assertFalse(starter.story_settings["showEntityBubbles"])

    def test_authoring_routes_export_and_download_without_exposing_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            service = self._service(root)
            app = create_app(frontend_dist=root / "missing-frontend", cors_origins=[])
            with patch("api.v1.world_package_routes.AUTHORING", service):
                client = TestClient(app)
                catalog = client.get("/api/v1/world-packages/authoring/assets")
                self.assertEqual(catalog.status_code, 200)
                self.assertNotIn("path", catalog.text)
                exported = client.post("/api/v1/world-packages/authoring/export", json={
                    **self._payload(),
                    "assets": [{"type": "worldbooks", "name": "测试世界书"}],
                    "world_premise": "测试梗概",
                    "opening": "从这里开始。",
                })
                self.assertEqual(exported.status_code, 200, exported.text)
                result = exported.json()
                downloaded = client.get(result["download_url"])
                self.assertEqual(downloaded.status_code, 200)
                self.assertTrue(downloaded.content.startswith(b"PK"))

    def test_official_route_creates_story_through_package_service(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            authoring = self._service(root)
            self._add_official_definition(root)
            package_service = WorldPackageService(root / "data" / "world_packages", root / "data")
            app = create_app(frontend_dist=root / "missing-frontend", cors_origins=[])

            def make_save(name: str) -> str:
                path = root / "data" / "saves" / f"Save_{name}"
                path.mkdir(parents=True)
                return str(path)

            fake = {"session_id": "official-session", "chat_messages": [], "state": {}, "story_settings": {}}
            with patch("api.v1.world_package_routes.AUTHORING", authoring), \
                 patch("api.v1.world_package_routes.SERVICE", package_service), \
                 patch("api.v1.world_package_routes.init_save_folder", side_effect=make_save), \
                 patch("api.v1.world_package_routes.start_prepared_game", return_value=fake):
                client = TestClient(app)
                listed = client.get("/api/v1/world-packages").json()
                self.assertEqual(listed["official_packages"][0]["official_id"], "official_demo")
                started = client.post(
                    "/api/v1/world-packages/official/official_demo/start",
                    json={"save_name": "官方开局"},
                )
            self.assertEqual(started.status_code, 200, started.text)
            self.assertTrue((root / "data" / "saves" / "Save_官方开局" / "world_package.json").is_file())


if __name__ == "__main__":
    unittest.main()
