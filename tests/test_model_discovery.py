import json
import unittest

from core.model_connections.discovery import ModelDiscoveryService
from core.model_connections.models import ConnectionProfile


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class ModelDiscoveryTests(unittest.TestCase):
    def profile(self):
        return ConnectionProfile(
            id="profile_1", name="测试接口", category="text",
            protocol="openai_compatible", base_url="http://model.test/v1",
            api_key="secret", default_model="model-b",
        )

    def test_discovers_sorts_deduplicates_and_caches_models(self):
        calls = []

        def opener(request, timeout):
            calls.append((request.full_url, request.headers.get("Authorization"), timeout))
            return _Response({"data": [{"id": "model-b"}, {"id": "model-a"}, {"id": "model-b"}]})

        service = ModelDiscoveryService(opener=opener)
        first = service.discover(self.profile())
        second = service.discover(self.profile())
        self.assertEqual(first.models, ("model-a", "model-b"))
        self.assertTrue(first.available)
        self.assertTrue(second.cached)
        self.assertEqual(calls, [("http://model.test/v1/models", "Bearer secret", 12)])

    def test_failure_is_non_blocking_for_manual_entry(self):
        def opener(_request, timeout):
            raise OSError("not supported")

        result = ModelDiscoveryService(opener=opener).discover(self.profile())
        self.assertFalse(result.available)
        self.assertIn("仍可手动填写", result.message)


if __name__ == "__main__":
    unittest.main()
