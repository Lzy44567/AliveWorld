"""Persisted preference workshop session registry."""

from __future__ import annotations

import json
from pathlib import Path

from core.preference_workshop import PreferenceWorkshop
from utils.file_io import DATA_DIR


WORKSHOP_DIR = Path(DATA_DIR) / "preferences" / "workshops"
active_preference_workshops: dict[str, PreferenceWorkshop] = {}


def load_preference_workshop(workshop_id: str) -> PreferenceWorkshop | None:
    if workshop_id in active_preference_workshops:
        return active_preference_workshops[workshop_id]
    path = WORKSHOP_DIR / f"{workshop_id}.json"
    if not path.exists():
        return None
    try:
        workshop = PreferenceWorkshop.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError):
        return None
    active_preference_workshops[workshop_id] = workshop
    return workshop


def find_resumable(profile: dict) -> tuple[PreferenceWorkshop | None, bool]:
    exact = []
    stale = []
    if WORKSHOP_DIR.exists():
        for path in WORKSHOP_DIR.glob("*.json"):
            workshop = load_preference_workshop(path.stem)
            if not workshop or not workshop.dirty or workshop.published:
                continue
            (exact if workshop.is_based_on(profile) else stale).append(workshop)
    if exact:
        return max(exact, key=lambda item: item.updated_at), False
    for workshop in sorted(stale, key=lambda item: item.updated_at, reverse=True):
        try:
            workshop.rebase(profile)
            workshop.save_session(WORKSHOP_DIR)
            return workshop, True
        except ValueError:
            continue
    return None, False
