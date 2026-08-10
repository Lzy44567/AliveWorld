import io
import json
import unittest
from urllib.error import URLError
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.update_checker import check_for_updates, is_newer, parse_version, select_release
from main import create_app


class UpdateVersionTests(unittest.TestCase):
    def test_orders_development_beta_release_candidate_and_stable(self):
        self.assertTrue(is_newer("1.5.0-beta.1", "1.5.0-dev.12"))
        self.assertTrue(is_newer("1.5.0-rc.1", "1.5.0-beta.2"))
        self.assertTrue(is_newer("1.5.0", "1.5.0-rc.9"))
        self.assertFalse(is_newer("1.5.0-dev.11", "1.5.0-dev.12"))
        self.assertFalse(is_newer("1.4.9", "1.5.0-dev.1"))

    def test_rejects_non_version_release_tags(self):
        self.assertIsNone(parse_version("nightly"))
        releases = [
            {"tag_name": "nightly", "draft": False, "prerelease": True},
            {"tag_name": "v1.5.0-beta.1", "draft": False, "prerelease": True},
        ]
        selected = select_release(releases)
        self.assertEqual(selected["tag_name"], "v1.5.0-beta.1")

    def test_stable_channel_excludes_prereleases(self):
        releases = [
            {"tag_name": "v2.0.0-beta.1", "draft": False, "prerelease": True},
            {"tag_name": "v1.5.0", "draft": False, "prerelease": False},
        ]
        selected = select_release(releases, include_prerelease=False)
        self.assertEqual(selected["tag_name"], "v1.5.0")

    @staticmethod
    def _response(payload):
        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()

        return Response(json.dumps(payload).encode("utf-8"))

    def test_public_release_repository_is_preferred_and_exposes_safe_assets(self):
        release = {
            "tag_name": "v1.5.0-dev.20", "draft": False, "prerelease": True,
            "name": "Bridge", "html_url": "https://github.com/Lzy44567/AliveWorld-Releases/releases/tag/v1.5.0-dev.20",
            "assets": [{
                "name": "AliveWorld-1.5.0-dev.20-windows-x64.zip",
                "browser_download_url": "https://github.com/Lzy44567/AliveWorld-Releases/releases/download/v1.5.0-dev.20/AliveWorld.zip",
                "size": 123, "digest": "sha256:abc",
            }],
        }
        with patch("core.update_checker.urlopen", return_value=self._response([release])) as mocked:
            result = check_for_updates(current_version="1.5.0-dev.19")
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(result["release_source"], "public-releases")
        self.assertEqual(result["assets"][0]["digest"], "sha256:abc")

    def test_empty_or_unreachable_public_repository_falls_back_to_legacy(self):
        legacy = [{
            "tag_name": "v1.5.0-dev.19", "draft": False, "prerelease": True,
            "html_url": "https://github.com/Lzy44567/AliveWorld/releases/tag/v1.5.0-dev.19",
            "assets": [],
        }]
        with patch("core.update_checker.urlopen", side_effect=[
            URLError("temporary"), self._response(legacy),
        ]) as mocked:
            result = check_for_updates(current_version="1.5.0-dev.14")
        self.assertEqual(mocked.call_count, 2)
        self.assertTrue(result["update_available"])
        self.assertEqual(result["release_source"], "legacy-public-source")


class UpdateRouteTests(unittest.TestCase):
    def test_route_returns_read_only_release_result(self):
        result = {
            "current_version": "1.5.0-dev.12",
            "latest_version": "1.5.0-beta.1",
            "update_available": True,
            "release_url": "https://github.com/Lzy44567/AliveWorld/releases/tag/v1.5.0-beta.1",
        }
        with patch("api.v1.update_routes.check_for_updates", return_value=result):
            client = TestClient(create_app(frontend_dist="missing"))
            response = client.get("/api/v1/updates/check")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), result)

    def test_route_failure_does_not_impersonate_latest_state(self):
        from core.update_checker import UpdateCheckError

        with patch(
            "api.v1.update_routes.check_for_updates",
            side_effect=UpdateCheckError("暂时无法连接 GitHub；这不会影响游戏。"),
        ):
            client = TestClient(create_app(frontend_dist="missing"))
            response = client.get("/api/v1/updates/check")
        self.assertEqual(response.status_code, 503)
        self.assertIn("不会影响游戏", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
