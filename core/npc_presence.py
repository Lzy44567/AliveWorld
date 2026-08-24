"""Deterministic lifecycle for the current-scene NPC radar."""

from __future__ import annotations

from typing import Any


DEPARTURE_MARKERS = (
    "已离开", "已经离开", "未出现", "未参与", "不在场", "离开现场",
    "未来不会再", "已退场", "已死亡", "死亡", "被带离",
)


class NpcPresenceTracker:
    """Keep the radar focused without deleting characters or story history."""

    def __init__(self, *, stale_turns: int = 3):
        self.stale_turns = max(2, int(stale_turns))
        self.absent_turns: dict[str, int] = {}

    @staticmethod
    def _status_text(value: Any) -> str:
        if isinstance(value, dict):
            return ", ".join(f"{key}:{item}" for key, item in value.items())
        return str(value or "").strip()

    @staticmethod
    def _mentioned(name: str, text: str) -> bool:
        clean = str(name or "").strip().casefold()
        return bool(clean and clean in text.casefold())

    @staticmethod
    def _departed(status: str) -> bool:
        return any(marker in status for marker in DEPARTURE_MARKERS)

    def reconcile(
        self,
        current: dict[str, str],
        updates: Any,
        *,
        story_text: str = "",
        player_action: str = "",
    ) -> dict[str, str]:
        current = dict(current or {})
        normalized = {
            str(name).strip(): self._status_text(status)
            for name, status in (updates.items() if isinstance(updates, dict) else [])
            if str(name).strip()
        }
        turn_text = f"{player_action}\n{story_text}"

        for name, status in normalized.items():
            if self._departed(status):
                current.pop(name, None)
                self.absent_turns.pop(name, None)
                continue
            if name not in current or self._mentioned(name, turn_text):
                current[name] = status
                self.absent_turns[name] = 0

        for name in list(current):
            status = current[name]
            if self._departed(status):
                current.pop(name, None)
                self.absent_turns.pop(name, None)
                continue
            if self._mentioned(name, turn_text):
                if name in normalized:
                    current[name] = normalized[name]
                self.absent_turns[name] = 0
                continue
            missing = self.absent_turns.get(name, 0) + 1
            if missing >= self.stale_turns:
                current.pop(name, None)
                self.absent_turns.pop(name, None)
            else:
                self.absent_turns[name] = missing
        return current

    def export_state(self) -> dict[str, Any]:
        return {"absent_turns": dict(self.absent_turns), "stale_turns": self.stale_turns}

    def load_state(self, value: Any) -> None:
        value = value if isinstance(value, dict) else {}
        raw = value.get("absent_turns", {})
        self.absent_turns = {
            str(name): max(0, int(turns))
            for name, turns in (raw.items() if isinstance(raw, dict) else [])
            if str(name).strip()
        }
