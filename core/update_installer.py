"""Safe preparation and handoff for portable AliveWorld updates."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from core.update_runtime import request_update_exit
from core.update_checker import parse_version
from utils.runtime_paths import PATHS, RuntimePaths
from utils.sys_logger import get_logger
from utils.version import APP_VERSION


class UpdateInstallError(RuntimeError):
    """A safe message for update preparation or handoff failures."""


class UpdateCancelled(UpdateInstallError):
    """The player cancelled an in-progress download."""


@dataclass(frozen=True)
class PreparedUpdate:
    version: str
    archive_name: str
    archive_path: str
    staging_app: str
    sha256: str


def _select_windows_assets(release: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    version = str(release.get("latest_version") or "").strip()
    expected = f"AliveWorld-{version}-windows-x64.zip"
    assets = release.get("assets") or []
    archive = next((item for item in assets if item.get("name") == expected), None)
    sidecar = next((item for item in assets if item.get("name") == f"{expected}.sha256"), None)
    if not archive or not sidecar:
        raise UpdateInstallError("该版本缺少 Windows 便携包或 SHA-256 校验文件。")
    digest = str(archive.get("digest") or "").lower().strip()
    if not digest.startswith("sha256:") or len(digest.removeprefix("sha256:")) != 64:
        raise UpdateInstallError("官方附件缺少可信的 SHA-256 摘要，已拒绝自动安装。")
    return archive, sidecar


def _safe_extract(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive) as package:
        members = package.infolist()
        if not members:
            raise UpdateInstallError("更新压缩包为空。")
        for member in members:
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise UpdateInstallError("更新压缩包包含不安全的符号链接。")
            target = (destination / member.filename).resolve()
            if target != destination_root and destination_root not in target.parents:
                raise UpdateInstallError("更新压缩包包含不安全的文件路径。")
        package.extractall(destination)
    roots = [item for item in destination.iterdir() if item.is_dir()]
    if len(roots) != 1 or roots[0].name != "AliveWorld":
        raise UpdateInstallError("更新压缩包结构不正确：必须只有 AliveWorld 根目录。")
    app_root = roots[0]
    if not (app_root / "AliveWorld.exe").is_file() or not (app_root / "_internal").is_dir():
        raise UpdateInstallError("更新包缺少 AliveWorld.exe 或运行环境。")
    if (app_root / "UserData").exists():
        raise UpdateInstallError("公开更新包不应包含 UserData，已拒绝安装。")
    return app_root


class UpdateManager:
    def __init__(
        self,
        paths: RuntimePaths = PATHS,
        *,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.paths = paths
        self.opener = opener
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._cancel_event = threading.Event()
        self._prepared: PreparedUpdate | None = None
        self._state: dict[str, Any] = {
            "status": "idle",
            "supported": bool(paths.frozen and os.name == "nt"),
            "progress": 0,
            "downloaded": 0,
            "total": 0,
            "message": "尚未开始下载。",
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            result = dict(self._state)
            if self._prepared:
                result["prepared"] = {
                    "version": self._prepared.version,
                    "archive_name": self._prepared.archive_name,
                    "sha256": self._prepared.sha256,
                }
            return result

    def _set(self, **values: Any) -> None:
        with self._lock:
            self._state.update(values)

    def start_prepare(self, release: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise UpdateInstallError("更新正在下载，请稍候。")
            if not self._state["supported"]:
                raise UpdateInstallError("源码运行模式只检查更新；一键安装仅用于 Windows 便携版。")
            self._prepared = None
            self._cancel_event.clear()
            self._state.update(
                status="downloading",
                progress=0,
                downloaded=0,
                total=0,
                version=str(release.get("latest_version") or ""),
                message="正在准备下载……",
                error=None,
            )
            self._thread = threading.Thread(
                target=self._prepare_worker,
                args=(release,),
                name="aliveworld-update-download",
                daemon=True,
            )
            self._thread.start()
        return self.snapshot()

    def _prepare_worker(self, release: dict[str, Any]) -> None:
        try:
            prepared = self.prepare(release)
            with self._lock:
                self._prepared = prepared
                self._state.update(
                    status="ready",
                    progress=100,
                    message="更新已下载并通过校验，可以安装。",
                    error=None,
                )
        except UpdateCancelled as exc:
            self._set(status="cancelled", progress=0, message=str(exc), error=None)
        except Exception as exc:
            message = str(exc) if isinstance(exc, UpdateInstallError) else "更新准备失败，请稍后重试。"
            get_logger().error(
                "更新准备失败：%s: %s",
                type(exc).__name__,
                exc,
                exc_info=not isinstance(exc, UpdateInstallError),
            )
            self._set(status="failed", message=message, error=message)

    def _download(
        self,
        url: str,
        target: Path,
        *,
        expected_size: int = 0,
        report_progress: bool = True,
    ) -> None:
        request = Request(url, headers={"User-Agent": f"AliveWorld/{APP_VERSION}"})
        target.parent.mkdir(parents=True, exist_ok=True)
        downloaded = 0
        with self.opener(request, timeout=30) as response, target.open("wb") as output:
            total = expected_size or int(response.headers.get("Content-Length") or 0)
            if report_progress:
                self._set(total=total)
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                if self._cancel_event.is_set():
                    raise UpdateCancelled("更新下载已取消。")
                output.write(chunk)
                downloaded += len(chunk)
                if report_progress:
                    progress = int(downloaded * 100 / total) if total else 0
                    self._set(
                        downloaded=downloaded,
                        progress=min(progress, 99),
                        message=f"正在下载更新…… {downloaded / 1024 / 1024:.1f} MB",
                    )
        if expected_size and downloaded != expected_size:
            raise UpdateInstallError("更新下载不完整，文件大小与官方记录不一致。")

    def prepare(self, release: dict[str, Any]) -> PreparedUpdate:
        archive_asset, sha_asset = _select_windows_assets(release)
        version = str(release["latest_version"])
        if parse_version(version) is None:
            raise UpdateInstallError("发布版本号格式无效。")
        cache_root = self.paths.user_root / "update-cache" / version
        if cache_root.exists():
            shutil.rmtree(cache_root)
        cache_root.mkdir(parents=True, exist_ok=True)
        archive_path = cache_root / str(archive_asset["name"])
        sidecar_path = cache_root / str(sha_asset["name"])
        self._download(
            str(archive_asset["url"]),
            archive_path,
            expected_size=int(archive_asset.get("size") or 0),
        )
        self._set(status="verifying", message="正在校验更新完整性……")
        self._download(
            str(sha_asset["url"]),
            sidecar_path,
            expected_size=int(sha_asset.get("size") or 0),
            report_progress=False,
        )
        digest = hashlib.sha256()
        with archive_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                if self._cancel_event.is_set():
                    raise UpdateCancelled("更新下载已取消。")
                digest.update(chunk)
        actual = digest.hexdigest()
        api_digest = str(archive_asset["digest"]).lower().removeprefix("sha256:")
        sidecar_parts = sidecar_path.read_text(encoding="ascii", errors="ignore").strip().split()
        sidecar_digest = sidecar_parts[0].lower() if sidecar_parts else ""
        if len(sidecar_digest) != 64 or any(character not in "0123456789abcdef" for character in sidecar_digest):
            raise UpdateInstallError("SHA-256 校验文件格式无效。")
        if actual != api_digest or actual != sidecar_digest:
            raise UpdateInstallError("更新文件 SHA-256 校验失败，已拒绝安装。")
        if self._cancel_event.is_set():
            raise UpdateCancelled("更新下载已取消。")
        staging_root = cache_root / "staging"
        app_root = _safe_extract(archive_path, staging_root)
        bundled_version = app_root / "_internal" / "VERSION"
        if not bundled_version.is_file() or bundled_version.read_text(encoding="utf-8").strip() != version:
            raise UpdateInstallError("更新包内部版本与发布版本不一致。")
        return PreparedUpdate(
            version=version,
            archive_name=archive_path.name,
            archive_path=str(archive_path),
            staging_app=str(app_root),
            sha256=actual,
        )

    def cancel(self) -> dict[str, Any]:
        with self._lock:
            if self._state.get("status") not in {"downloading", "verifying"}:
                raise UpdateInstallError("当前没有可以取消的更新下载。")
            self._cancel_event.set()
            self._state.update(status="cancelling", message="正在取消下载……")
        return self.snapshot()

    def begin_install(self) -> dict[str, Any]:
        with self._lock:
            prepared = self._prepared
            if not prepared or self._state.get("status") != "ready":
                raise UpdateInstallError("更新尚未下载并校验完成。")
        executable = Path(sys.executable).resolve()
        install_dir = executable.parent
        if self.paths.user_root.resolve() != (install_dir / "UserData").resolve():
            raise UpdateInstallError("无法确认便携版数据目录，已取消安装。")
        token = secrets.token_urlsafe(24)
        temp_root = Path(tempfile.gettempdir())
        for stale in temp_root.glob("AliveWorld-update-*"):
            if stale.is_dir():
                shutil.rmtree(stale, ignore_errors=True)
        handoff_root = temp_root / f"AliveWorld-update-{secrets.token_hex(8)}"
        handoff_root.mkdir(parents=True)
        helper = handoff_root / "AliveWorldUpdater.exe"
        bundled_helper = install_dir / "AliveWorldUpdater.exe"
        if not bundled_helper.is_file():
            raise UpdateInstallError("当前便携包缺少独立更新助手，无法自动安装。")
        shutil.copy2(bundled_helper, helper)
        confirmation = self.paths.user_root / "update-cache" / prepared.version / "healthy.json"
        manifest = {
            "token": token,
            "version": prepared.version,
            "current_pid": os.getpid(),
            "install_dir": str(install_dir),
            "user_data": str(self.paths.user_root),
            "staging_app": prepared.staging_app,
            "confirmation": str(confirmation),
        }
        manifest_path = handoff_root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        subprocess.Popen(
            [str(helper), str(manifest_path)],
            cwd=str(handoff_root),
            close_fds=True,
        )
        self._set(status="installing", message="正在退出 AliveWorld 并安装更新……")
        request_update_exit()
        return {"status": "installing", "message": self._state["message"]}


UPDATE_MANAGER = UpdateManager()
