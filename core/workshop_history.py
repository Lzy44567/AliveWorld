"""Read-only projections of completed workshop session files."""

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any


def published_history(
    directory: Path,
    loader: Callable[[str], Any | None],
    matches: Callable[[Any], bool],
) -> list[dict[str, Any]]:
    """Return safe conversation snapshots without making old drafts editable."""
    records: list[dict[str, Any]] = []
    for path in directory.glob("*.json") if directory.exists() else []:
        workshop = loader(path.stem)
        if not workshop or not getattr(workshop, "published", False) or not matches(workshop):
            continue
        messages = []
        for item in getattr(workshop, "messages", []):
            if not isinstance(item, dict) or item.get("role") not in {"user", "assistant", "ai"}:
                continue
            messages.append({
                "role": "assistant" if item.get("role") == "ai" else item.get("role"),
                "content": str(item.get("content", "")),
            })
        records.append({
            "workshop_id": str(workshop.id),
            "published_at": str(getattr(workshop, "updated_at", "")),
            "messages": copy.deepcopy(messages),
        })
    records.sort(key=lambda item: item["published_at"], reverse=True)
    return records
