"""Discarded successful turns, kept separate from canonical story history."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from core.capture_source import turn_identity


def archive_attempt(snapshot, turns):
    previous = snapshot.get("story_turns", [])
    previous_ids = {turn_identity(turn) for turn in previous}
    removed = [turn for turn in turns if turn_identity(turn) not in previous_ids]
    if not removed:
        return None
    # Include state: the same turn number is not necessarily the same starting world.
    origin = {"turns": [turn_identity(turn) for turn in previous], "state": snapshot["state"]}
    origin_id = hashlib.sha256(json.dumps(origin, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {
        "id": uuid4().hex,
        "origin_id": origin_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "turns": copy.deepcopy(removed),
    }
