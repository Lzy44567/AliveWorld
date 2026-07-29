"""Runtime engine factory backed by task routing."""

from __future__ import annotations

from typing import Callable

from core.ai_engine import AIEngine
from utils.runtime_paths import PATHS

from .models import ConnectionSnapshot, ResolvedConnection
from .repository import ConnectionRepository


class ModelConnectionRuntime:
    def __init__(
        self,
        repository: ConnectionRepository,
        engine_factory: Callable[[dict[str, str]], object] = AIEngine,
    ):
        self.repository = repository
        self.engine_factory = engine_factory
        self.snapshot: ConnectionSnapshot | None = None
        self._engines: dict[tuple[str, str, str, str], object] = {}

    def reload(self, *, persist_migration: bool = False) -> ConnectionSnapshot:
        self.snapshot = self.repository.load(persist_migration=persist_migration)
        self._engines.clear()
        return self.snapshot

    def ensure_migrated(self) -> ConnectionSnapshot:
        self.snapshot = self.repository.ensure_migrated()
        self._engines.clear()
        return self.snapshot

    def resolved(self, task: str) -> ResolvedConnection | None:
        snapshot = self.snapshot or self.reload()
        return self.repository.resolve(snapshot, task)

    def engine(self, task: str):
        resolved = self.resolved(task)
        if not resolved or resolved.profile.category != "text":
            return None
        config = resolved.ai_config()
        if not all(config.get(key) for key in ("api_key", "base_url", "model")):
            return None
        cache_key = (
            resolved.profile.id,
            config["base_url"],
            config["api_key"],
            config["model"],
        )
        if cache_key not in self._engines:
            self._engines[cache_key] = self.engine_factory(config)
        return self._engines[cache_key]

    def memory_config(self) -> dict[str, int]:
        raw = self.repository.read_raw()
        try:
            value = max(8192, int(raw.get("memory_context_limit") or 32768))
        except (TypeError, ValueError):
            value = 32768
        return {"context_limit": value}


model_runtime = ModelConnectionRuntime(ConnectionRepository(PATHS.config_file))


def get_task_engine(task: str):
    return model_runtime.engine(task)
