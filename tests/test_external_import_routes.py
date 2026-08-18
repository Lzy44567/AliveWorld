import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.external_formats import ExternalAssetImportService
from main import create_app


class ExternalImportRouteTests(unittest.TestCase):
    def test_preview_then_import_character(self):
        source = {
            "spec": "chara_card_v2",
            "spec_version": "2.0",
            "data": {"name": "API角色", "description": "测试", "first_mes": "你好", "tags": []},
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            service = ExternalAssetImportService(root / "data")
            app = create_app(frontend_dist=root / "missing", cors_origins=[])
            payload = json.dumps(source, ensure_ascii=False).encode()
            with patch("api.v1.external_import_routes.SERVICE", service):
                client = TestClient(app)
                preview = client.post(
                    "/api/v1/external-assets/inspect?filename=card.json&kind=character",
                    content=payload,
                    headers={"Content-Type": "application/octet-stream"},
                )
                self.assertEqual(preview.status_code, 200)
                self.assertEqual(preview.json()["suggested_name"], "API角色")
                imported = client.post(
                    "/api/v1/external-assets/import?filename=card.json&kind=character&name=API%E8%A7%92%E8%89%B2",
                    content=payload,
                    headers={"Content-Type": "application/octet-stream"},
                )
                self.assertEqual(imported.status_code, 200)
                duplicate = client.post(
                    "/api/v1/external-assets/import?filename=card.json&kind=character",
                    content=payload,
                    headers={"Content-Type": "application/octet-stream"},
                )
                self.assertEqual(duplicate.status_code, 409)

    def test_wrong_kind_has_clear_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            service = ExternalAssetImportService(root / "data")
            app = create_app(frontend_dist=root / "missing", cors_origins=[])
            with patch("api.v1.external_import_routes.SERVICE", service):
                response = TestClient(app).post(
                    "/api/v1/external-assets/inspect?filename=card.png&kind=lorebook",
                    content=b"\x89PNG\r\n\x1a\n",
                    headers={"Content-Type": "application/octet-stream"},
                )
            self.assertEqual(response.status_code, 400)
            self.assertIn("PNG", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
