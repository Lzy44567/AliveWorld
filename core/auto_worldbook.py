"""Save-local fallback worldbook for stories started without authored assets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core.worldbook import save_worldbook_atomic


AUTO_CAPTURE_FILENAME = "_本局自动设定.yml"
AUTO_CAPTURE_NAME = "本局自动设定"


def is_auto_capture_worldbook(data: Any) -> bool:
    return isinstance(data, dict) and data.get("is_auto_capture_book") is True


def ensure_auto_capture_worldbook(save_dir: str | Path) -> Path:
    """Create one editable fallback inside this save, never in global assets."""
    directory = Path(save_dir) / "worldbooks"
    directory.mkdir(parents=True, exist_ok=True)
    for path in sorted(directory.glob("*.yml")):
        try:
            if is_auto_capture_worldbook(yaml.safe_load(path.read_text(encoding="utf-8")) or {}):
                return path
        except (OSError, yaml.YAMLError):
            continue

    path = directory / AUTO_CAPTURE_FILENAME
    if path.exists():
        index = 2
        while (directory / f"_本局自动设定_{index}.yml").exists():
            index += 1
        path = directory / f"_本局自动设定_{index}.yml"
    save_worldbook_atomic(path, {
        "name": AUTO_CAPTURE_NAME,
        "tags": ["本局专属", "自动记录"],
        "overview": "",
        "axioms": [],
        "entries": [],
        "is_active": True,
        "is_auto_capture_book": True,
    })
    return path


def select_capture_worldbook(save_dir: str | Path, *, create_fallback: bool = False) -> Path | None:
    """Prefer an authored active book; use the save-local automatic book last."""
    directory = Path(save_dir) / "worldbooks"
    authored: list[Path] = []
    automatic: list[Path] = []
    for path in sorted(directory.glob("*.yml")) if directory.exists() else []:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if data.get("is_active", True) is False:
            continue
        (automatic if is_auto_capture_worldbook(data) else authored).append(path)
    if authored:
        return authored[0]
    if automatic:
        return automatic[0]
    return ensure_auto_capture_worldbook(save_dir) if create_fallback else None
