"""Stable identifiers for persisted chat messages."""

from __future__ import annotations

from typing import Any
from uuid import uuid4


def ensure_message_ids(messages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    seen: set[str] = set()
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        message_id = str(message.get("id", "")).strip()
        if not message_id or message_id in seen:
            message_id = f"message_{uuid4().hex[:12]}"
            message["id"] = message_id
        seen.add(message_id)
    return messages or []
