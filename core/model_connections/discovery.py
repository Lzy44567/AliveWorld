"""Best-effort model discovery for OpenAI-compatible text connections."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable
from urllib.request import Request, urlopen

from .models import ConnectionProfile


@dataclass(frozen=True, slots=True)
class ModelDiscoveryResult:
    available: bool
    models: tuple[str, ...] = ()
    message: str = ""
    cached: bool = False

    def public_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "models": list(self.models),
            "message": self.message,
            "cached": self.cached,
        }


class ModelDiscoveryService:
    def __init__(self, *, ttl_seconds: float = 300, opener: Callable[..., Any] = urlopen):
        self.ttl_seconds = max(0.0, float(ttl_seconds))
        self.opener = opener
        self._cache: dict[str, tuple[float, ModelDiscoveryResult]] = {}
        self._lock = RLock()

    def discover(self, profile: ConnectionProfile, *, refresh: bool = False) -> ModelDiscoveryResult:
        if profile.category != "text" or profile.protocol != "openai_compatible":
            return ModelDiscoveryResult(False, message="该接口不支持文本模型发现")
        if not profile.base_url:
            return ModelDiscoveryResult(False, message="请先填写接口地址")
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(profile.id)
            if cached and not refresh and now - cached[0] < self.ttl_seconds:
                result = cached[1]
                return ModelDiscoveryResult(result.available, result.models, result.message, True)
        try:
            request = Request(profile.base_url.rstrip("/") + "/models", method="GET")
            if profile.api_key:
                request.add_header("Authorization", f"Bearer {profile.api_key}")
            with self.opener(request, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
            models = tuple(sorted({
                str(item.get("id") or "").strip()
                for item in payload.get("data", [])
                if isinstance(item, dict) and str(item.get("id") or "").strip()
            }, key=str.casefold))
            result = ModelDiscoveryResult(
                bool(models), models,
                "已读取可用模型" if models else "接口返回了空模型列表，可继续手动填写",
            )
        except Exception as exc:
            result = ModelDiscoveryResult(
                False,
                message=f"接口不支持模型列表或暂时无法读取；仍可手动填写。{str(exc)[:160]}",
            )
        with self._lock:
            self._cache[profile.id] = (now, result)
        return result

    def invalidate(self, profile_id: str) -> None:
        with self._lock:
            self._cache.pop(profile_id, None)

