import socket
import unittest
from unittest.mock import Mock, patch

import desktop_launcher


class DesktopLauncherTests(unittest.TestCase):
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

    def test_migration_refreshes_frontend_with_cache_busting_url(self):
        window = Mock()
        with (
            patch.object(desktop_launcher.time, "sleep"),
            patch.object(desktop_launcher, "discover_legacy_root", return_value="legacy"),
            patch.object(desktop_launcher, "prompt_legacy_migration", return_value=object()),
            patch.object(desktop_launcher.time, "time", return_value=1234),
        ):
            desktop_launcher.offer_legacy_migration_after_load(
                window,
                "http://127.0.0.1:8000/",
            )

        window.load_url.assert_called_once_with(
            "http://127.0.0.1:8000/?legacy_import=1234"
        )


if __name__ == "__main__":
    unittest.main()
