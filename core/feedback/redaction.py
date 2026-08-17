"""Defence-in-depth redaction for player-previewed diagnostic content."""

from __future__ import annotations

import re
from typing import Any


SECRET_KEY_MARKERS = (
    "api_key", "apikey", "authorization", "secret", "access_token", "refresh_token",
    "github_token", "password", "custom_headers",
)

_TEXT_RULES = (
    (re.compile(r"(?i)(bearer\s+)[^\s,;\"']+"), r"\1***"),
    (re.compile(r"(?i)((?:api[_ -]?key|authorization|access[_ -]?token|secret|password)\s*[:=]\s*)[^\s,;\"']+"), r"\1***"),
    (re.compile(r"\b(?:sk|sess|ghp|github_pat)-?[A-Za-z0-9_-]{12,}\b", re.I), "***"),
    (re.compile(r"(?i)C:\\Users\\[^\\\s]+"), "%USERPROFILE%"),
    (re.compile(r"(?i)/home/[^/\s]+"), "$HOME"),
)

_SUSPECT_SECRET = re.compile(
    r"(?i)(?:bearer\s+(?!\*{3})\S+|(?:api[_ -]?key|authorization|access[_ -]?token|password)\s*[:=]\s*(?!\*{3})\S+|\b(?:sk|ghp|github_pat)-?[A-Za-z0-9_-]{12,}\b)"
)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            lowered = str(key).lower()
            result[str(key)] = "***" if any(marker in lowered for marker in SECRET_KEY_MARKERS) else redact(item)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    if not isinstance(value, str):
        return value
    text = value
    for pattern, replacement in _TEXT_RULES:
        text = pattern.sub(replacement, text)
    return text


def contains_suspected_secret(value: Any) -> bool:
    if isinstance(value, dict):
        return any(contains_suspected_secret(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_suspected_secret(item) for item in value)
    return bool(_SUSPECT_SECRET.search(value)) if isinstance(value, str) else False
