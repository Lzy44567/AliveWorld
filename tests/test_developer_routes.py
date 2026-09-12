import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.developer_access import DeveloperAccess
from core.prompt_studio import PromptOverrideStore
from main import create_app


class DeveloperRoutesTests(unittest.TestCase):
    def test_prompt_routes_require_unlock_and_apply_versioned_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            access = DeveloperAccess(root / "access.json")
            store = PromptOverrideStore(root / "overrides.json")
            with patch("api.v1.developer_routes.developer_access", access), patch(
                "api.v1.developer_routes.prompt_store", store
            ):
                client = TestClient(create_app(cors_origins=[]))
                self.assertEqual(client.get("/api/v1/developer/prompts").status_code, 401)
                setup = client.post("/api/v1/developer/setup", json={"password": "testing-password"})
                self.assertEqual(setup.status_code, 200)
                headers = {"Authorization": f"Bearer {setup.json()['token']}"}
                listing = client.get("/api/v1/developer/prompts", headers=headers)
                self.assertEqual(listing.status_code, 200)
                item = next(value for value in listing.json()["slices"] if value["id"] == "story.future.core")
                changed = item["baseline"] + "\n附加测试规则"
                saved = client.put(
                    "/api/v1/developer/prompts/story.future.core",
                    headers=headers, json={"content": changed},
                )
                self.assertEqual(saved.json()["overrideVersion"], 1)
                active = client.get("/api/v1/developer/prompts", headers=headers).json()["slices"]
                item = next(value for value in active if value["id"] == "story.future.core")
                self.assertEqual(item["source"], "override")
                self.assertEqual(item["active"], changed)
                restored = client.delete("/api/v1/developer/prompts/story.future.core", headers=headers)
                self.assertTrue(restored.json()["restored"])

    def test_retired_unprotected_prompt_endpoint_cannot_read_or_write(self):
        client = TestClient(create_app(cors_origins=[]))
        self.assertEqual(client.get("/api/v1/lobby/prompts").status_code, 410)
        self.assertEqual(client.post("/api/v1/lobby/prompts", json={"prompts": {}}).status_code, 410)


if __name__ == "__main__":
    unittest.main()
