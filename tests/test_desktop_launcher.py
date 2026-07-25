import socket
import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
