"""Process-local handoff signal shared by the update API and desktop launcher."""

from __future__ import annotations

import threading


UPDATE_EXIT_EVENT = threading.Event()


def request_update_exit() -> None:
    UPDATE_EXIT_EVENT.set()


def reset_update_exit() -> None:
    UPDATE_EXIT_EVENT.clear()
