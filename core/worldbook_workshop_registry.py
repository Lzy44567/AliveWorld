"""Registry and path maintenance for persisted worldbook workshop sessions."""

from __future__ import annotations

import json
from pathlib import Path

from core.worldbook_workshop import WorldbookWorkshop
from core.workshop_history import published_history
from utils.file_io import DATA_DIR


WORKSHOP_DIR = Path(DATA_DIR) / "workshops"
active_workshops: dict[str, WorldbookWorkshop] = {}


def load_worldbook_workshop(workshop_id: str) -> WorldbookWorkshop | None:
    if workshop_id in active_workshops:
        return active_workshops[workshop_id]
    path = WORKSHOP_DIR / f"{workshop_id}.json"
    if not path.exists():
        return None
    try:
        workshop = WorldbookWorkshop.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None
    active_workshops[workshop.id] = workshop
    return workshop


def list_worldbook_workshop_history(target_path: Path) -> list[dict]:
    target = target_path.resolve()
    return published_history(
        WORKSHOP_DIR,
        load_worldbook_workshop,
        lambda item: item.target_path.resolve() == target,
    )


def retarget_workshops(old_path: str | Path, new_path: str | Path, *, recursive: bool = False) -> int:
    """Keep unpublished workshop drafts attached after an asset/save rename."""
    old_root = Path(old_path).resolve()
    new_root = Path(new_path).resolve()
    sessions: dict[str, WorldbookWorkshop] = dict(active_workshops)
    if WORKSHOP_DIR.exists():
        for path in WORKSHOP_DIR.glob("*.json"):
            if path.stem in sessions:
                continue
            workshop = load_worldbook_workshop(path.stem)
            if workshop:
                sessions[path.stem] = workshop
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
        if replacement is None:
            continue
        workshop.target_path = replacement
        workshop.save_session(WORKSHOP_DIR)
        active_workshops[workshop.id] = workshop
        changed += 1
    return changed
