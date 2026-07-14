"""Discovery and safe resolution for the cross-save image library."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib

import yaml

from utils.file_io import CHAR_DIR, DATA_DIR, get_all_saves


GLOBAL_IMAGE_LIBRARY_DIR = Path(DATA_DIR) / "image_library"


@dataclass(frozen=True)
class ImageLibraryScope:
    id: str
    name: str
    kind: str
    root: Path


def list_library_scopes() -> list[ImageLibraryScope]:
    scopes = [ImageLibraryScope("global", "全局图片资源", "global", GLOBAL_IMAGE_LIBRARY_DIR)]
    seen = {"global"}
    for save_name, data in get_all_saves().items():
        root = Path(str(data.get("_save_dir", "")))
        if not root.is_dir():
            continue
        scope_id = root.name
        if scope_id in seen:
            continue
        seen.add(scope_id)
        scopes.append(ImageLibraryScope(scope_id, str(save_name), "save", root))
    return scopes


def resolve_library_scope(scope_id: str) -> ImageLibraryScope:
    for scope in list_library_scopes():
        if scope.id == scope_id:
            return scope
    raise ValueError("图片资源分区不存在")


def list_global_portrait_assets() -> list[dict]:
    """Return character-owned portraits that are not necessarily backed by tasks."""
    root = Path(CHAR_DIR)
    portraits_dir = root / "_portraits"
    if not portraits_dir.is_dir():
        return []
    referenced: dict[str, str] = {}
    for card in root.glob("*.yml"):
        try:
            data = yaml.safe_load(card.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        portrait = data.get("portrait") if isinstance(data, dict) else None
        filename = Path(str((portrait or {}).get("path", ""))).name
        if filename and (portraits_dir / filename).is_file():
            referenced[filename] = str(data.get("name", card.stem))
    assets = []
    for path in sorted(portraits_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        digest = hashlib.sha256(path.name.encode("utf-8")).hexdigest()[:12]
        assets.append({
            "id": f"portrait_asset_{digest}",
            "filename": path.name,
            "character_name": referenced.get(path.name, "未关联角色"),
            "referenced": path.name in referenced,
        })
    return assets
