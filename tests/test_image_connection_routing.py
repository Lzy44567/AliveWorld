import unittest
from types import SimpleNamespace
from unittest.mock import patch

from api.v1.image_generation_routes import _route_image_task


class ImageConnectionRoutingTests(unittest.TestCase):
    def test_backend_route_overrides_browser_supplied_comfyui_address(self):
        resolved = SimpleNamespace(profile=SimpleNamespace(
            id="image-main", name="本机 ComfyUI", protocol="comfyui",
            base_url="http://127.0.0.1:8188",
        ))
        with patch("core.model_connections.runtime.get_task_connection", return_value=resolved):
            data = _route_image_task({
                "provider_id": "comfyui",
                "provider_options": {"base_url": "http://malicious.invalid", "checkpoint": "test.safetensors"},
            })
        self.assertEqual(data["provider_options"]["base_url"], "http://127.0.0.1:8188")
        self.assertEqual(data["provider_options"]["connection_id"], "image-main")
        self.assertEqual(data["provider_options"]["checkpoint"], "test.safetensors")


if __name__ == "__main__":
    unittest.main()
