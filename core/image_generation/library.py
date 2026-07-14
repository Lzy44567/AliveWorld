"""Discovery and safe resolution for the cross-save image library."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from utils.file_io import DATA_DIR, get_all_saves


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
