"""Registry and path maintenance for persisted worldbook workshop sessions."""

from __future__ import annotations

import json
from pathlib import Path

from core.worldbook_workshop import WorldbookWorkshop
from utils.file_io import DATA_DIR


WORKSHOP_DIR = Path(DATA_DIR) / "workshops"
active_workshops: dict[str, WorldbookWorkshop] = {}


def retarget_workshops(old_path: str | Path, new_path: str | Path, *, recursive: bool = False) -> int:
    """Keep unpublished workshop drafts attached after an asset/save rename."""
    old_root = Path(old_path).resolve()
    new_root = Path(new_path).resolve()
    sessions: dict[str, WorldbookWorkshop] = dict(active_workshops)
    if WORKSHOP_DIR.exists():
        for path in WORKSHOP_DIR.glob("*.json"):
            if path.stem in sessions:
                continue
            try:
                sessions[path.stem] = WorldbookWorkshop.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError, KeyError):
                continue
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
