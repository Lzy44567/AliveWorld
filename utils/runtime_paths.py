"""Runtime resource and user-data paths for source and packaged builds."""

from __future__ import annotations

import os
import shutil
import sys
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class RuntimePaths:
    resource_root: Path
    user_root: Path
    data_dir: Path
    config_file: Path
    log_dir: Path
    frontend_dist: Path
    frozen: bool


def resolve_runtime_paths(
    *,
    environ: Mapping[str, str] | None = None,
    frozen: bool | None = None,
    module_file: str | Path | None = None,
    executable_file: str | Path | None = None,
) -> RuntimePaths:
    env = dict(os.environ if environ is None else environ)
    source_root = Path(module_file or __file__).resolve().parents[1]
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    bundled_root = Path(getattr(sys, "_MEIPASS", source_root)) if is_frozen else source_root
    resource_root = Path(env.get("ALIVEWORLD_RESOURCE_DIR") or bundled_root).expanduser().resolve()

    if env.get("ALIVEWORLD_USER_DIR"):
        user_root = Path(env["ALIVEWORLD_USER_DIR"]).expanduser().resolve()
    elif is_frozen:
        # The ZIP distribution is deliberately portable: programs and personal
        # data remain together, while upgrades replace only the program files.
        executable_path = Path(executable_file or sys.executable).resolve()
        user_root = (executable_path.parent / "UserData").resolve()
    else:
        # Source development keeps the confirmed repository layout and existing data.
        user_root = source_root

    frontend_dist = Path(
        env.get("ALIVEWORLD_FRONTEND_DIST") or resource_root / "aliveworld-ui" / "dist"
    ).expanduser().resolve()
    return RuntimePaths(
        resource_root=resource_root,
        user_root=user_root,
        data_dir=user_root / "data",
        config_file=user_root / "config.yml",
        log_dir=user_root / "logs",
        frontend_dist=frontend_dist,
        frozen=is_frozen,
    )


def prepare_runtime_layout(paths: RuntimePaths) -> None:
    paths.user_root.mkdir(parents=True, exist_ok=True)
    paths.log_dir.mkdir(parents=True, exist_ok=True)
    for relative in (
        "characters",
        "entities",
        "image_library",
        "image_workflows",
        "preferences",
        "saves",
        "styles",
        "worldbooks",
        "workshops",
        "asset_workshops",
        "cache",
        "models",
    ):
        (paths.data_dir / relative).mkdir(parents=True, exist_ok=True)

    example_config = paths.resource_root / "config.example.yml"
    if not paths.config_file.exists() and example_config.is_file():
        shutil.copy2(example_config, paths.config_file)
    upgrade_retired_config_defaults(paths.config_file)

    bundled_data = paths.resource_root / "data"
    if bundled_data.resolve() == paths.data_dir.resolve() or not bundled_data.is_dir():
        return
    for pattern in ("*.template.yml", "*.template.json"):
        for source in bundled_data.rglob(pattern):
            target = paths.data_dir / source.relative_to(bundled_data)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)


def upgrade_retired_config_defaults(config_file: Path) -> None:
    """Repair defaults shipped by older portable builds without touching custom providers."""
    if not config_file.is_file():
        return
    try:
        data = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return
    if not isinstance(data, dict):
        return
    changed = False
    if str(data.get("api_key") or "").strip() == "YOUR_API_KEY":
        data["api_key"] = ""
        changed = True
    base_url = str(data.get("base_url") or "").strip().rstrip("/")
    if base_url in {"https://api.deepseek.com", "https://api.deepseek.com/v1"}:
        if str(data.get("model") or "").strip() == "deepseek-chat":
            data["model"] = "deepseek-v4-flash"
            changed = True
    if changed:
        config_file.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


PATHS = resolve_runtime_paths()
prepare_runtime_layout(PATHS)

