"""Privacy and executable-content gate for world-package exports and imports."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


FORBIDDEN_PARTS = frozenset({
    ".env", "config.yml", "config.yaml", "settings.json", "session_state.json",
    "logs", "saves", "preferences", "workshops", "asset_workshops", "cache", "models",
})
FORBIDDEN_SUFFIXES = frozenset({".exe", ".dll", ".bat", ".cmd", ".ps1", ".sh", ".py", ".pyd", ".so"})
SECRET_KEYS = frozenset({"api_key", "apikey", "access_token", "refresh_token", "authorization", "password", "secret"})
SECRET_TEXT = re.compile(r"(?i)(?:sk-[A-Za-z0-9_-]{16,}|(?:api[_-]?key|authorization|password|secret)\s*[:=]\s*['\"]?[^\s'\"]{8,})")
ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]|/(?:home|Users)/[^/\s]+/)", re.IGNORECASE)


@dataclass(frozen=True)
class PrivacyIssue:
    code: str
    message: str


def _structured_secrets(value: Any, path: str = "") -> list[PrivacyIssue]:
    issues: list[PrivacyIssue] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).strip().casefold()
            child_path = f"{path}.{key}" if path else str(key)
            if key_text in SECRET_KEYS and str(child or "").strip():
                issues.append(PrivacyIssue("secret_field", f"包含敏感字段：{child_path}"))
            else:
                issues.extend(_structured_secrets(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(_structured_secrets(child, f"{path}[{index}]"))
    return issues


def scan_asset(relative_path: str, content: bytes) -> list[PrivacyIssue]:
    path = PurePosixPath(relative_path)
    issues: list[PrivacyIssue] = []
    lower_parts = {part.casefold() for part in path.parts}
    blocked = sorted(lower_parts & FORBIDDEN_PARTS)
    if blocked:
        issues.append(PrivacyIssue("private_path", f"路径属于私人数据目录或文件：{', '.join(blocked)}"))
    if path.suffix.casefold() in FORBIDDEN_SUFFIXES:
        issues.append(PrivacyIssue("executable", f"首版世界包禁止可执行内容：{path.name}"))
    if b"\x00" in content[:4096] and path.suffix.casefold() not in {".png", ".jpg", ".jpeg", ".webp"}:
        issues.append(PrivacyIssue("unexpected_binary", f"不支持的二进制资产：{path.name}"))
        return issues
    if path.suffix.casefold() not in {".yml", ".yaml", ".json", ".txt", ".md"}:
        return issues
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        issues.append(PrivacyIssue("invalid_text", f"文本资产不是 UTF-8：{path.name}"))
        return issues
    if SECRET_TEXT.search(text):
        issues.append(PrivacyIssue("secret_text", f"文本疑似包含密钥：{path.name}"))
    if ABSOLUTE_PATH.search(text):
        issues.append(PrivacyIssue("absolute_path", f"文本疑似包含本机用户绝对路径：{path.name}"))
    try:
        structured = json.loads(text) if path.suffix.casefold() == ".json" else yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError):
        structured = None
    issues.extend(_structured_secrets(structured))
    unique = {(item.code, item.message): item for item in issues}
    return list(unique.values())
