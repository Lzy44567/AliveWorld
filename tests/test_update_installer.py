import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from core.update_installer import PreparedUpdate, UpdateInstallError, UpdateManager, _safe_extract
from updater_main import apply_update
from utils.runtime_paths import RuntimePaths


class DownloadResponse(io.BytesIO):
    def __init__(self, payload: bytes):
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def make_package(version: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as package:
        package.writestr("AliveWorld/AliveWorld.exe", b"new executable")
        package.writestr("AliveWorld/_internal/VERSION", version)
        package.writestr("AliveWorld/_internal/runtime.txt", "ready")
    return output.getvalue()


def runtime_paths(root: Path, *, frozen: bool = True) -> RuntimePaths:
    user = root / "UserData"
    return RuntimePaths(
        resource_root=root,
        user_root=user,
        data_dir=user / "data",
        config_file=user / "config.yml",
        log_dir=user / "logs",
        frontend_dist=root / "dist",
        frozen=frozen,
    )


class UpdatePreparationTests(unittest.TestCase):
    def test_downloads_double_verifies_and_safely_extracts_portable_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            version = "1.5.0-dev.20"
            archive = make_package(version)
            digest = hashlib.sha256(archive).hexdigest()
            sidecar = f"{digest}  AliveWorld-{version}-windows-x64.zip\n".encode("ascii")
            payloads = {"https://github.com/archive": archive, "https://github.com/sha": sidecar}

            def opener(request, timeout=0):
                self.assertEqual(timeout, 30)
                return DownloadResponse(payloads[request.full_url])

            manager = UpdateManager(runtime_paths(root), opener=opener)
            prepared = manager.prepare({
                "latest_version": version,
                "assets": [
                    {
                        "name": f"AliveWorld-{version}-windows-x64.zip",
                        "url": "https://github.com/archive",
                        "size": len(archive),
                        "digest": f"sha256:{digest}",
                    },
                    {
                        "name": f"AliveWorld-{version}-windows-x64.zip.sha256",
                        "url": "https://github.com/sha",
                        "size": len(sidecar),
                        "digest": "sha256:unused",
                    },
                ],
            })
            self.assertEqual(prepared.version, version)
            self.assertEqual(prepared.sha256, digest)
            self.assertTrue((Path(prepared.staging_app) / "AliveWorld.exe").is_file())

    def test_rejects_archive_digest_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            version = "1.5.0-dev.20"
            archive = make_package(version)
            digest = hashlib.sha256(archive).hexdigest()
            sidecar = f"{digest}  package.zip\n".encode("ascii")
            payloads = {"https://github.com/archive": archive, "https://github.com/sha": sidecar}
            manager = UpdateManager(
                runtime_paths(root),
                opener=lambda request, timeout=0: DownloadResponse(payloads[request.full_url]),
            )
            release = {
                "latest_version": version,
                "assets": [
                    {"name": f"AliveWorld-{version}-windows-x64.zip", "url": "https://github.com/archive", "size": len(archive), "digest": f"sha256:{'0' * 64}"},
                    {"name": f"AliveWorld-{version}-windows-x64.zip.sha256", "url": "https://github.com/sha", "size": len(sidecar)},
                ],
            }
            with self.assertRaisesRegex(UpdateInstallError, "校验失败"):
                manager.prepare(release)

    def test_rejects_zip_path_traversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("../outside.txt", "bad")
            with self.assertRaisesRegex(UpdateInstallError, "不安全"):
                _safe_extract(archive, root / "extract")

    def test_source_mode_cannot_start_self_install(self):
        with tempfile.TemporaryDirectory() as temporary:
            manager = UpdateManager(runtime_paths(Path(temporary), frozen=False))
            with self.assertRaisesRegex(UpdateInstallError, "源码运行模式"):
                manager.start_prepare({"latest_version": "1.5.0-dev.20"})

    def test_cancel_marks_active_download_without_touching_userdata(self):
        with tempfile.TemporaryDirectory() as temporary:
            manager = UpdateManager(runtime_paths(Path(temporary)))
            manager._state["status"] = "downloading"
            result = manager.cancel()
            self.assertEqual(result["status"], "cancelling")
            self.assertTrue(manager._cancel_event.is_set())

    def test_install_handoff_uses_bundled_standalone_helper_and_requests_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            install = root / "AliveWorld"
            user = install / "UserData"
            staging = user / "update-cache" / "1.5.0-dev.20" / "staging" / "AliveWorld"
            staging.mkdir(parents=True)
            user.mkdir(parents=True, exist_ok=True)
            executable = install / "AliveWorld.exe"
            helper = install / "AliveWorldUpdater.exe"
            executable.write_bytes(b"app")
            helper.write_bytes(b"standalone helper")
            manager = UpdateManager(runtime_paths(install))
            manager._prepared = PreparedUpdate(
                version="1.5.0-dev.20",
                archive_name="package.zip",
                archive_path=str(root / "package.zip"),
                staging_app=str(staging),
                sha256="a" * 64,
            )
            manager._state["status"] = "ready"

            with patch("core.update_installer.sys.executable", str(executable)), patch(
                "core.update_installer.tempfile.gettempdir", return_value=str(root / "temp")
            ), patch("core.update_installer.subprocess.Popen") as spawn, patch(
                "core.update_installer.request_update_exit"
            ) as request_exit:
                result = manager.begin_install()

            self.assertEqual(result["status"], "installing")
            launched = Path(spawn.call_args.args[0][0])
            self.assertEqual(launched.name, "AliveWorldUpdater.exe")
            self.assertEqual(launched.read_bytes(), b"standalone helper")
            request_exit.assert_called_once_with()


class UpdateHelperTests(unittest.TestCase):
    def _layout(self, root: Path, version: str) -> tuple[Path, Path, Path, Path]:
        install = root / "AliveWorld"
        user = install / "UserData"
        staging = user / "update-cache" / version / "staging" / "AliveWorld"
        (install / "_internal").mkdir(parents=True)
        (install / "AliveWorld.exe").write_text("old", encoding="utf-8")
        (install / "_internal" / "VERSION").write_text("old-version", encoding="utf-8")
        (user / "data").mkdir(parents=True)
        (user / "data" / "sentinel.txt").write_text("keep", encoding="utf-8")
        (staging / "_internal").mkdir(parents=True)
        (staging / "AliveWorld.exe").write_text("new", encoding="utf-8")
        (staging / "_internal" / "VERSION").write_text(version, encoding="utf-8")
        confirmation = user / "update-cache" / version / "healthy.json"
        return install, user, staging, confirmation

    def _manifest(self, root: Path, install: Path, user: Path, staging: Path, confirmation: Path, version: str) -> Path:
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({
            "token": "test-token",
            "version": version,
            "current_pid": 123,
            "install_dir": str(install),
            "user_data": str(user),
            "staging_app": str(staging),
            "confirmation": str(confirmation),
        }), encoding="utf-8")
        return manifest

    def test_success_preserves_userdata_and_removes_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            version = "1.5.0-dev.20"
            install, user, staging, confirmation = self._layout(root, version)
            manifest = self._manifest(root, install, user, staging, confirmation, version)

            class HealthyProcess:
                def __init__(self, *_args, **_kwargs):
                    confirmation.write_text(json.dumps({"token": "test-token", "version": version}), encoding="utf-8")

                def poll(self):
                    return None

            with patch("updater_main._wait_for_exit", return_value=True), patch(
                "updater_main.subprocess.Popen", side_effect=HealthyProcess
            ):
                apply_update(manifest)

            self.assertEqual((install / "AliveWorld.exe").read_text(encoding="utf-8"), "new")
            self.assertEqual((user / "data" / "sentinel.txt").read_text(encoding="utf-8"), "keep")
            self.assertFalse((user / "update-backups" / f"before-{version}").exists())

    def test_failed_health_check_rolls_back_and_relaunches_old_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            version = "1.5.0-dev.20"
            install, user, staging, confirmation = self._layout(root, version)
            manifest = self._manifest(root, install, user, staging, confirmation, version)

            class FailedProcess:
                def poll(self):
                    return 1

                def terminate(self):
                    return None

                def wait(self, timeout=0):
                    return 1

            with patch("updater_main._wait_for_exit", return_value=True), patch(
                "updater_main.subprocess.Popen", return_value=FailedProcess()
            ), patch("updater_main.time.monotonic", side_effect=[0, 100]):
                with self.assertRaisesRegex(RuntimeError, "启动验证"):
                    apply_update(manifest)

            self.assertEqual((install / "AliveWorld.exe").read_text(encoding="utf-8"), "old")
            self.assertEqual((user / "data" / "sentinel.txt").read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
