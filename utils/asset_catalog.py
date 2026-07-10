"""全局资产目录：个人 data 与可提交模板的统一读取入口。"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import yaml

from utils.file_io import BASE_DIR, CHAR_DIR, ENTITY_DIR, STYLE_DIR, WORLD_DIR


TEMPLATE_DIR = Path(BASE_DIR) / "templates"
PERSONAL_DIRS: Dict[str, Path] = {
    "worldbooks": Path(WORLD_DIR),
    "styles": Path(STYLE_DIR),
    "characters": Path(CHAR_DIR),
    "entities": Path(ENTITY_DIR),
}


def personal_asset_dir(asset_type: str) -> Optional[Path]:
    return PERSONAL_DIRS.get(asset_type)


def template_asset_dir(asset_type: str) -> Path:
    return TEMPLATE_DIR / asset_type


def _asset_name(path: Path) -> Optional[str]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    return data.get("name") if isinstance(data, dict) else None


def _find_by_name(directory: Optional[Path], asset_name: str) -> Optional[Path]:
    if not directory or not directory.exists():
        return None
    direct_path = directory / f"{asset_name}.yml"
    if direct_path.exists():
        return direct_path
    for path in directory.glob("*.yml"):
        if _asset_name(path) == asset_name:
            return path
    return None


def list_asset_names(asset_type: str) -> List[str]:
    names = set()
    for directory in (template_asset_dir(asset_type), personal_asset_dir(asset_type)):
        if not directory or not directory.exists():
            continue
        for path in directory.glob("*.yml"):
            name = _asset_name(path)
            if name:
                names.add(name)
    return sorted(names)


def resolve_asset_path(asset_type: str, asset_name: str) -> Optional[Path]:
    """优先使用用户自己的同名资产；没有时回退到受控模板。"""
    return _find_by_name(personal_asset_dir(asset_type), asset_name) or _find_by_name(template_asset_dir(asset_type), asset_name)


def resolve_template_path(asset_type: str, asset_name: str) -> Optional[Path]:
    return _find_by_name(template_asset_dir(asset_type), asset_name)
