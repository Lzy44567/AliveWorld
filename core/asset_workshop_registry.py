"""Persistence and resume lookup for non-worldbook asset workshops."""

from __future__ import annotations

import json
from pathlib import Path

from core.asset_workshop import AssetWorkshop, asset_revision, normalize_asset
from core.character_asset_write import character_revision
from core.workshop_history import published_history
from utils.file_io import DATA_DIR


WORKSHOP_DIR = Path(DATA_DIR) / "asset_workshops"
active_asset_workshops: dict[str, AssetWorkshop] = {}


def retarget_asset_workshops(old_path: str | Path, new_path: str | Path, *, recursive: bool = False) -> int:
    """Keep unpublished asset drafts attached after an asset or save rename."""
    old_root = Path(old_path).resolve()
    new_root = Path(new_path).resolve()
    sessions = dict(active_asset_workshops)
    for path in WORKSHOP_DIR.glob("*.json") if WORKSHOP_DIR.exists() else []:
        workshop = load_asset_workshop(path.stem)
        if workshop:
            sessions[workshop.id] = workshop
    changed = 0
    for workshop in sessions.values():
        target = workshop.target_path.resolve()
        replacement = None
        if target == old_root:
            replacement = new_root
        elif recursive:
            try:
                replacement = new_root / target.relative_to(old_root)
            except ValueError:
                pass
        if replacement is not None:
            workshop.target_path = replacement
            workshop.save_session(WORKSHOP_DIR)
            active_asset_workshops[workshop.id] = workshop
            changed += 1
    return changed


def load_asset_workshop(workshop_id: str) -> AssetWorkshop | None:
    if workshop_id in active_asset_workshops:
        workshop = active_asset_workshops[workshop_id]
        workshop.recover_publication(WORKSHOP_DIR)
        return workshop
    path = WORKSHOP_DIR / f"{workshop_id}.json"
    if not path.exists():
        return None
    try:
        workshop = AssetWorkshop.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None
    active_asset_workshops[workshop.id] = workshop
    workshop.recover_publication(WORKSHOP_DIR)
    return workshop


def find_resumable(asset_type: str, target_path: Path, source: dict) -> AssetWorkshop | None:
    target = target_path.resolve()
    current_revision = character_revision(source) if asset_type == 'characters' else asset_revision(normalize_asset(asset_type, source))
    candidates: list[AssetWorkshop] = []
    for path in WORKSHOP_DIR.glob("*.json") if WORKSHOP_DIR.exists() else []:
        workshop = load_asset_workshop(path.stem)
        if workshop and workshop.asset_type == asset_type and workshop.target_path.resolve() == target:
            if workshop.dirty and not workshop.published and workshop.source_revision == current_revision:
                candidates.append(workshop)
    return max(candidates, key=lambda item: item.updated_at) if candidates else None


def list_asset_workshop_history(asset_type: str, target_path: Path) -> list[dict]:
    target = target_path.resolve()
    return published_history(
        WORKSHOP_DIR,
        load_asset_workshop,
        lambda item: item.asset_type == asset_type and item.target_path.resolve() == target,
    )
