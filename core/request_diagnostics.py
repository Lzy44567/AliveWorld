"""Bounded process-local, content-free request observations for developer UI."""
from collections import deque
from copy import deepcopy
from threading import Lock

_lock = Lock()
_recent = deque(maxlen=32)


def record_request(label, trace_id, metadata, error=None):
    metadata = metadata or {}
    if "budget" not in metadata:
        return
    with _lock:
        _recent.append({"task": label, "traceId": trace_id, "status": "error" if error else "success",
                        "budget": deepcopy(metadata["budget"]),
                        "usage": deepcopy(metadata.get("normalizedUsage", {})),
                        "elapsedMs": metadata.get("elapsedMs")})


def recent_requests():
    with _lock:
        return deepcopy(list(reversed(_recent)))
