import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from fastapi.testclient import TestClient

from api.v1 import model_connection_routes
from core.model_connections.models import TaskRoute
from core.model_connections.repository import (
    MAIN_PROFILE_ID,
    PREFERENCE_PROFILE_ID,
    ConnectionRepository,
)
from core.model_connections.router import RouteResolutionError
from core.model_connections.runtime import ModelConnectionRuntime
from main import create_app


class ConnectionRepositoryTests(unittest.TestCase):
    def _repository(self, root: Path, text: str) -> ConnectionRepository:
        path = root / "config.yml"
        path.write_text(text, encoding="utf-8")
        return ConnectionRepository(path)

    def test_legacy_config_migrates_with_backup_and_inheritance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository = self._repository(
                root,
                "\n".join(
                    [
                        "api_key: main-secret",
                        "base_url: https://api.deepseek.com",
                        "model: story-model",
                        "memory_api_key: ''",
                        "memory_base_url: ''",
                        "memory_model: memory-model",
                        "preference_api_key: preference-secret",
                        "preference_base_url: https://preference.example/v1",
                        "preference_model: preference-model",
                        "image_api_url: http://127.0.0.1:8188",
                        "memory_context_limit: 50000",
                    ]
                ),
            )

            snapshot = repository.ensure_migrated()

            self.assertTrue((root / "config.pre-model-connections.yml").is_file())
            stored = yaml.safe_load((root / "config.yml").read_text(encoding="utf-8"))
            self.assertIn("model_connections", stored)
            self.assertEqual(repository.resolve(snapshot, "story").profile.id, MAIN_PROFILE_ID)
            memory = repository.resolve(snapshot, "memory")
            self.assertEqual(memory.profile.id, MAIN_PROFILE_ID)
            self.assertEqual(memory.model, "memory-model")
            preference = repository.resolve(snapshot, "preference")
            self.assertEqual(preference.profile.id, PREFERENCE_PROFILE_ID)
            self.assertNotEqual(preference.profile.id, MAIN_PROFILE_ID)
            self.assertEqual(repository.resolve(snapshot, "workshop").model, "story-model")
            self.assertEqual(stored["api_key"], "main-secret")

    def test_public_config_hides_all_secrets_and_legacy_reveal_preserves_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository = self._repository(
                root,
                "api_key: main-secret\nbase_url: http://localhost:1234/v1\nmodel: local\n",
            )
            public = repository.ensure_migrated().public_dict()
            rendered = str(public)
            self.assertNotIn("main-secret", rendered)
            self.assertTrue(public["profiles"][0]["api_key_configured"])
            self.assertTrue(repository.legacy_public_config()["apiReady"])
            self.assertEqual(repository.reveal_legacy_secret("apiKey"), "main-secret")
            self.assertEqual(repository.reveal_legacy_secret("memoryApiKey"), "")

    def test_local_text_endpoint_is_ready_without_api_key(self):
        with tempfile.TemporaryDirectory() as temp:
            repository = self._repository(
                Path(temp),
                "api_key: ''\nbase_url: http://127.0.0.1:7861/v1\nmodel: local-model\n",
            )

            public = repository.legacy_public_config()

            self.assertFalse(public["apiKeyConfigured"])
            self.assertTrue(public["apiReady"])

    def test_legacy_update_preserves_custom_profiles_and_task_routes(self):
        with tempfile.TemporaryDirectory() as temp:
            repository = self._repository(
                Path(temp),
                "api_key: main\nbase_url: https://example.test/v1\nmodel: story\n",
            )
            extra = repository.create_profile(
                {
                    "name": "工坊专用",
                    "category": "text",
                    "protocol": "openai_compatible",
                    "base_url": "https://workshop.example/v1",
                    "api_key": "workshop-secret",
                    "default_model": "workshop-model",
                }
            )
            repository.set_route("workshop", TaskRoute(connection_id=extra.id))

            repository.update_legacy(
                api_key=None,
                base_url="https://changed.example/v1",
                model="changed-story",
                memory_api_key=None,
                memory_base_url="",
                memory_model="summary-model",
                preference_api_key=None,
                preference_base_url="",
                preference_model="",
                image_api_url="http://127.0.0.1:8188",
                memory_context_limit=64000,
            )

            snapshot = repository.load()
            self.assertEqual(repository.resolve(snapshot, "workshop").profile.id, extra.id)
            self.assertEqual(repository.resolve(snapshot, "workshop").model, "workshop-model")
            self.assertEqual(repository.resolve(snapshot, "memory").model, "summary-model")

    def test_profile_name_route_category_and_in_use_delete_are_validated(self):
        with tempfile.TemporaryDirectory() as temp:
            repository = self._repository(
                Path(temp),
                "api_key: main\nbase_url: https://example.test/v1\nmodel: story\n",
            )
            repository.ensure_migrated()
            extra = repository.create_profile(
                {
                    "name": "便宜模型",
                    "category": "text",
                    "protocol": "openai_compatible",
                    "base_url": "https://cheap.example/v1",
                    "api_key": "cheap-secret",
                    "default_model": "cheap",
                }
            )
            with self.assertRaisesRegex(ValueError, "同名"):
                repository.clone_profile(extra.id, "便宜模型")
            repository.set_route(
                "memory",
                TaskRoute(connection_id=extra.id, model_override="summary"),
            )
            self.assertEqual(repository.resolve(repository.load(), "memory").model, "summary")
            with self.assertRaisesRegex(ValueError, "仍用于"):
                repository.delete_profile(extra.id)
            image = repository.resolve(repository.load(), "image_generation").profile
            with self.assertRaisesRegex(RouteResolutionError, "需要 text"):
                repository.set_route("memory", TaskRoute(connection_id=image.id))

    def test_runtime_reuses_profile_but_allows_task_model_override(self):
        with tempfile.TemporaryDirectory() as temp:
            repository = self._repository(
                Path(temp),
                "api_key: secret\nbase_url: https://example.test/v1\nmodel: story-model\n"
                "memory_model: summary-model\n",
            )
            created = []

            def factory(config):
                created.append(dict(config))
                return {"config": dict(config)}

            runtime = ModelConnectionRuntime(repository, engine_factory=factory)
            story = runtime.engine("story")
            memory = runtime.engine("memory")
            workshop = runtime.engine("workshop")

            self.assertEqual(story["config"]["model"], "story-model")
            self.assertEqual(memory["config"]["model"], "summary-model")
            self.assertIs(workshop, story)
            self.assertEqual(len(created), 2)


class ConnectionRouteTests(unittest.TestCase):
    def test_api_lists_masked_profiles_and_blocks_deleting_active_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository = ConnectionRepository(root / "config.yml")
            repository.path.write_text(
                "api_key: route-secret\nbase_url: https://example.test/v1\nmodel: story\n",
                encoding="utf-8",
            )
            app = create_app(frontend_dist=root / "missing", cors_origins=[])
            with (
                patch.object(model_connection_routes, "repository", repository),
                patch.object(model_connection_routes, "_refresh_runtime"),
                TestClient(app) as client,
            ):
                response = client.get("/api/v1/model-connections")
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("route-secret", response.text)
                profile_id = next(
                    item["id"]
                    for item in response.json()["profiles"]
                    if item["category"] == "text"
                )
                deleted = client.delete(f"/api/v1/model-connections/profiles/{profile_id}")
                self.assertEqual(deleted.status_code, 409)
                self.assertIn("故事正文", deleted.json()["detail"])

    def test_api_profile_crud_secret_reveal_and_task_assignment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository = ConnectionRepository(root / "config.yml")
            repository.path.write_text(
                "api_key: main\nbase_url: https://example.test/v1\nmodel: story\n",
                encoding="utf-8",
            )
            app = create_app(frontend_dist=root / "missing", cors_origins=[])
            with (
                patch.object(model_connection_routes, "repository", repository),
                patch.object(model_connection_routes, "_refresh_runtime"),
                TestClient(app) as client,
            ):
                created = client.post(
                    "/api/v1/model-connections/profiles",
                    json={
                        "name": "工坊模型",
                        "category": "text",
                        "protocol": "openai_compatible",
                        "providerHint": "custom",
                        "baseUrl": "https://workshop.example/v1",
                        "apiKey": "workshop-secret",
                        "defaultModel": "workshop-v1",
                    },
                )
                self.assertEqual(created.status_code, 200)
                profile_id = created.json()["id"]
                self.assertNotIn("workshop-secret", created.text)

                revealed = client.post(
                    f"/api/v1/model-connections/profiles/{profile_id}/reveal-secret"
                )
                self.assertEqual(revealed.json()["value"], "workshop-secret")

                routed = client.post(
                    "/api/v1/model-connections/routes/workshop",
                    json={
                        "connectionId": profile_id,
                        "inheritFrom": "",
                        "modelOverride": "workshop-v2",
                    },
                )
                self.assertEqual(routed.status_code, 200)
                resolved = repository.resolve(repository.load(), "workshop")
                self.assertEqual(resolved.profile.id, profile_id)
                self.assertEqual(resolved.model, "workshop-v2")

                updated = client.post(
                    f"/api/v1/model-connections/profiles/{profile_id}",
                    json={
                        "name": "工坊模型",
                        "category": "text",
                        "protocol": "openai_compatible",
                        "providerHint": "custom",
                        "baseUrl": "https://workshop.example/v1",
                        "apiKey": None,
                        "defaultModel": "workshop-v3",
                    },
                )
                self.assertEqual(updated.status_code, 200)
                self.assertTrue(updated.json()["api_key_configured"])
                self.assertEqual(repository.reveal_profile_secret(profile_id), "workshop-secret")


if __name__ == "__main__":
    unittest.main()
