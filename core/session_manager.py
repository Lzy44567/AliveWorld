# core/session_manager.py
from contextlib import contextmanager
from pathlib import Path
from threading import Lock, RLock
from typing import Dict
from core.game_session import GameSession

# 全局存储所有正在运行的沙盒推演实例
active_sessions: Dict[str, GameSession] = {}
_save_sessions: Dict[str, str] = {}
_mutation_locks: Dict[str, Lock] = {}
_registry_lock = RLock()


class MutationBusyError(RuntimeError):
    pass


def save_identity(save_dir_path: str) -> str:
    return str(Path(save_dir_path).resolve()).casefold()


def register_session(session_id: str, game: GameSession) -> None:
    with _registry_lock:
        active_sessions[session_id] = game
        _save_sessions[save_identity(game.save_dir_path)] = session_id


def existing_session(save_dir_path: str) -> tuple[str, GameSession] | None:
    identity = save_identity(save_dir_path)
    with _registry_lock:
        session_id = _save_sessions.get(identity)
        game = active_sessions.get(session_id or "")
        if game is None and session_id:
            _save_sessions.pop(identity, None)
        return (session_id, game) if session_id and game else None


def unregister_session(session_id: str) -> None:
    with _registry_lock:
        game = active_sessions.pop(session_id, None)
        if game:
            _save_sessions.pop(save_identity(game.save_dir_path), None)


def retarget_session(session_id: str, old_path: str, new_path: str) -> None:
    with _registry_lock:
        if _save_sessions.get(save_identity(old_path)) == session_id:
            _save_sessions.pop(save_identity(old_path), None)
        if session_id in active_sessions:
            _save_sessions[save_identity(new_path)] = session_id


@contextmanager
def mutation_guard(namespace: str, identity: str, *, blocking: bool = False):
    """Serialize one mutable aggregate while allowing different keys to overlap."""
    key = f"{namespace}:{identity}"
    with _registry_lock:
        lock = _mutation_locks.setdefault(key, Lock())
    if not lock.acquire(blocking=blocking):
        raise MutationBusyError("该对象已有操作正在执行，请等待完成后再试")
    try:
        yield
    finally:
        lock.release()
