"""Single application version source shared by the backend and build tooling."""

from __future__ import annotations

from utils.runtime_paths import PATHS


def read_app_version() -> str:
    version_file = PATHS.resource_root / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


APP_VERSION = read_app_version()
