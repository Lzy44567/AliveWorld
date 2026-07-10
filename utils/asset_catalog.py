"""全局资产目录：个人 data 与可提交模板的统一读取入口。"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import yaml

from utils.file_io import BASE_DIR, CHAR_DIR, ENTITY_DIR, STYLE_DIR, WORLD_DIR


PERSONAL_DIRS: Dict[str, Path] = {
    "worldbooks": Path(WORLD_DIR),
    "styles": Path(STYLE_DIR),
    "characters": Path(CHAR_DIR),
    "entities": Path(ENTITY_DIR),
}


def personal_asset_dir(asset_type: str) -> Optional[Path]:
    return PERSONAL_DIRS.get(asset_type)


def _asset_name(path: Path) -> Optional[str]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    return data.get("name") if isinstance(data, dict) else None


def _is_template(path: Path) -> bool:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return False
    tags = data.get("tags", []) if isinstance(data, dict) else []
    return path.name.endswith(".template.yml") or data.get("is_template") is True or "模板" in tags


def _find_by_name(directory: Optional[Path], asset_name: str, templates_only: bool = False) -> Optional[Path]:
    if not directory or not directory.exists():
        return None
    candidates = [path for path in directory.glob("*.yml") if _asset_name(path) == asset_name]
    if templates_only:
        candidates = [path for path in candidates if _is_template(path)]
    else:
        candidates.sort(key=_is_template)
    return candidates[0] if candidates else None


def list_asset_names(asset_type: str) -> List[str]:
    names = set()
    directory = personal_asset_dir(asset_type)
    if not directory or not directory.exists():
        return []
    for path in directory.glob("*.yml"):
        name = _asset_name(path)
        if name:
            names.add(name)
    return sorted(names)


def resolve_asset_path(asset_type: str, asset_name: str) -> Optional[Path]:
    """优先使用同目录的个人同名资产；没有时回退到模板卡。"""
    return _find_by_name(personal_asset_dir(asset_type), asset_name)


def resolve_template_path(asset_type: str, asset_name: str) -> Optional[Path]:
    return _find_by_name(personal_asset_dir(asset_type), asset_name, templates_only=True)
