import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from main import create_app
from utils.version import APP_VERSION


class ProductionAppTests(unittest.TestCase):
    def _frontend_dist(self, root: Path) -> Path:
        dist = root / "dist"
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text("<html>aliveworld</html>", encoding="utf-8")
        (dist / "assets" / "app.js").write_text("window.alive = true", encoding="utf-8")
        return dist

    def test_one_port_serves_health_assets_and_spa_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            dist = self._frontend_dist(Path(temporary))
            client = TestClient(create_app(frontend_dist=dist, cors_origins=[]))

            health = client.get("/api/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["version"], APP_VERSION)
            self.assertIn("aliveworld", client.get("/").text)
            self.assertIn("aliveworld", client.get("/workshop/worldbook").text)
            self.assertIn("window.alive", client.get("/assets/app.js").text)
            self.assertEqual(client.get("/api/does-not-exist").status_code, 404)

    def test_cors_is_limited_to_explicit_development_origin(self):
        with tempfile.TemporaryDirectory() as temporary:
            dist = self._frontend_dist(Path(temporary))
            client = TestClient(
                create_app(
                    frontend_dist=dist,
                    cors_origins=["http://127.0.0.1:5173"],
                )
            )
            allowed = client.options(
                "/api/health",
                headers={
                    "Origin": "http://127.0.0.1:5173",
                    "Access-Control-Request-Method": "GET",
                },
            )
            self.assertEqual(
                allowed.headers.get("access-control-allow-origin"),
                "http://127.0.0.1:5173",
            )
            denied = client.options(
                "/api/health",
                headers={
                    "Origin": "https://example.invalid",
                    "Access-Control-Request-Method": "GET",
                },
            )
            self.assertNotIn("access-control-allow-origin", denied.headers)


if __name__ == "__main__":
    unittest.main()
