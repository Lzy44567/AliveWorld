"""Materialize explicit start selections before a new session becomes visible."""

from pathlib import Path

import yaml

from core.asset_lifecycle import AssetLifecycleError, filename_for_asset
from core.world_packages.provenance import refresh_local_instance_id
from core.worldbook import save_worldbook_atomic
from utils.asset_catalog import resolve_asset_path


def prepare_start_assets(selections: dict[str, str]) -> list[tuple[str, str, dict]]:
    prepared = []
    for kind, name in selections.items():
        if not name:
            continue
        source = resolve_asset_path(kind, name)
        if source is None:
            raise AssetLifecycleError(f"所选资产已不存在：{name}，请重新选择")
        try:
            data = yaml.safe_load(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise AssetLifecycleError(f"无法读取所选资产：{name}") from exc
        if not isinstance(data, dict):
            raise AssetLifecycleError(f"资产格式无效：{name}")
        data["is_active"] = True
        if kind == "characters":
            data["is_player"] = True
        refresh_local_instance_id(data)
        prepared.append((kind, filename_for_asset(name), data))
    return prepared


def write_start_assets(save_dir: str, prepared: list[tuple[str, str, dict]]) -> None:
    for kind, filename, data in prepared:
        path = Path(save_dir) / kind / filename
        if kind == "worldbooks":
            save_worldbook_atomic(path, data)
        else:
            path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
