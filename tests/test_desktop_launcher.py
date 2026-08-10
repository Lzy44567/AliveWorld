import socket
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import desktop_launcher


class DesktopLauncherTests(unittest.TestCase):
    def test_versioned_url_busts_frontend_cache(self):
        self.assertEqual(
            desktop_launcher.versioned_url("http://127.0.0.1:8000/"),
            f"http://127.0.0.1:8000/?app_version={desktop_launcher.APP_VERSION}",
        )

    def test_choose_port_skips_occupied_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.bind(("127.0.0.1", 0))
            port = occupied.getsockname()[1]
            selected = desktop_launcher.choose_port(port, attempts=20)
            self.assertGreater(selected, port)
            self.assertLess(selected, port + 20)

    def test_read_running_url_rejects_invalid_port_file(self):
        with patch.object(desktop_launcher, "PORT_FILE") as port_file:
            port_file.read_text.return_value = "invalid"
            self.assertIsNone(desktop_launcher.read_running_url())

    def test_server_config_does_not_require_console_streams(self):
        with patch("sys.stdout", None), patch("sys.stderr", None):
            server = desktop_launcher.create_server(object(), 8765)

        self.assertIsNone(server.config.log_config)
        self.assertFalse(server.config.access_log)
        self.assertEqual(server.config.port, 8765)

    def test_successful_update_writes_token_and_runtime_version_atomically(self):
        with tempfile.TemporaryDirectory() as temporary:
            confirmation = Path(temporary) / "healthy.json"
            with patch.dict("os.environ", {
                "ALIVEWORLD_UPDATE_CONFIRM_PATH": str(confirmation),
                "ALIVEWORLD_UPDATE_TOKEN": "token-123",
                "ALIVEWORLD_EXPECTED_VERSION": desktop_launcher.APP_VERSION,
            }, clear=False):
                desktop_launcher.confirm_successful_update()
            payload = json.loads(confirmation.read_text(encoding="utf-8"))
            self.assertEqual(payload["token"], "token-123")
            self.assertEqual(payload["version"], desktop_launcher.APP_VERSION)
            self.assertEqual(list(Path(temporary).glob("*.tmp-*")), [])

if __name__ == "__main__":
    unittest.main()
