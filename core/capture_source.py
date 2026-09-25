"""Persisted source-turn identity for asynchronous worldbook work."""
import hashlib
import json
from pathlib import Path


def turn_identity(turn):
    fields = {key: turn.get(key) for key in ("turn_id", "player", "story", "source_message_ids")}
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def source_is_current(save_dir, source_turn):
    """Fail closed on deleted, unreadable or replaced saves; turn numbers alone are reusable."""
    try:
        state = json.loads((Path(save_dir) / "session_state.json").read_text(encoding="utf-8"))
        turns = state.get("history", {}).get("story_turns", [])
        return any(isinstance(turn, dict) and turn_identity(turn) == turn_identity(source_turn) for turn in turns)
    except (OSError, ValueError, TypeError, AttributeError):
        return False
