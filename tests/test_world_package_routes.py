import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.world_packages import AssetSource, WorldPackageExporter, WorldPackageService, new_package_id
from main import create_app


class WorldPackageRouteTests(unittest.TestCase):
    def test_raw_file_preview_install_and_list(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "data"
            source = root / "world.yml"
            source.write_text("name: API测试世界\noverview: API测试\n", encoding="utf-8")
            archive = root / "api.aliveworld"
            WorldPackageExporter().export(
                archive,
                package={
                    "package_id": new_package_id(),
                    "version": "1.0.0",
                    "name": "API测试世界包",
                    "author": "自动验收",
                },
                assets=[AssetSource("worldbooks", source)],
            )
            service = WorldPackageService(data / "world_packages", data)
            app = create_app(frontend_dist=root / "missing-frontend", cors_origins=[])
            with patch("api.v1.world_package_routes.SERVICE", service):
                client = TestClient(app)
                payload = archive.read_bytes()
                preview = client.post(
                    "/api/v1/world-packages/inspect",
                    content=payload,
                    headers={"Content-Type": "application/octet-stream"},
                )
                self.assertEqual(preview.status_code, 200)
                self.assertEqual(preview.json()["status"], "new")
                installed = client.post(
                    "/api/v1/world-packages/import",
                    content=payload,
                    headers={"Content-Type": "application/octet-stream"},
                )
                self.assertEqual(installed.status_code, 200)
                packages = client.get("/api/v1/world-packages").json()["packages"]
                self.assertEqual([item["name"] for item in packages], ["API测试世界包"])

    def test_invalid_upload_has_clear_client_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            service = WorldPackageService(root / "data" / "world_packages", root / "data")
            app = create_app(frontend_dist=root / "missing-frontend", cors_origins=[])
            with patch("api.v1.world_package_routes.SERVICE", service):
                response = TestClient(app).post(
                    "/api/v1/world-packages/inspect",
                    content=b"not a package",
                    headers={"Content-Type": "application/octet-stream"},
                )
            self.assertEqual(response.status_code, 400)
            self.assertIn("有效", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
