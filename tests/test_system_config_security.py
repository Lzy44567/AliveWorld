import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from api.v1 import game_routes


class SystemConfigSecurityTests(unittest.TestCase):
    def test_secret_requires_explicit_reveal_endpoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_file = Path(temporary) / "config.yml"
            config_file.write_text("api_key: main-secret\n", encoding="utf-8")
            with patch.object(game_routes, "config_path", str(config_file)):
                hidden = game_routes.get_system_config()
                revealed = game_routes.reveal_system_config_secret(
                    game_routes.SecretRevealPayload(field="apiKey")
                )

            self.assertEqual(hidden["apiKey"], "")
            self.assertTrue(hidden["apiKeyConfigured"])
            self.assertEqual(revealed["value"], "main-secret")

    def test_secret_reveal_rejects_unknown_fields(self):
        with self.assertRaises(Exception) as raised:
            game_routes.reveal_system_config_secret(
                game_routes.SecretRevealPayload(field="arbitrary")
            )
        self.assertEqual(raised.exception.status_code, 400)

    def test_get_hides_secrets_and_blank_update_preserves_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_file = Path(temporary) / "config.yml"
            config_file.write_text(
                yaml.safe_dump(
                    {
                        "api_key": "main-secret",
                        "base_url": "https://example.test/v1",
                        "model": "story-model",
                        "memory_api_key": "memory-secret",
                        "preference_api_key": "preference-secret",
                    },
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )
            payload = game_routes.SystemConfigPayload(
                apiKey="",
                apiBaseUrl="https://new.example.test/v1",
                model="new-model",
                memoryApiKey="",
                preferenceApiKey="",
            )

            with (
                patch.object(game_routes, "config_path", str(config_file)),
                patch.object(game_routes, "active_sessions", {}),
            ):
                visible = game_routes.get_system_config()
                self.assertEqual(visible["apiKey"], "")
                self.assertTrue(visible["apiKeyConfigured"])
                self.assertEqual(visible["memoryApiKey"], "")
                self.assertTrue(visible["memoryApiKeyConfigured"])
                self.assertEqual(visible["preferenceApiKey"], "")
                self.assertTrue(visible["preferenceApiKeyConfigured"])

                game_routes.update_system_config(payload)

            stored = yaml.safe_load(config_file.read_text(encoding="utf-8"))
            self.assertEqual(stored["api_key"], "main-secret")
            self.assertEqual(stored["memory_api_key"], "memory-secret")
            self.assertEqual(stored["preference_api_key"], "preference-secret")
            self.assertEqual(stored["base_url"], "https://new.example.test/v1")
            self.assertEqual(stored["model"], "new-model")


if __name__ == "__main__":
    unittest.main()
