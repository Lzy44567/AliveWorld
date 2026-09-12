"""Local developer-mode password gate. This prevents accidents, not reverse engineering."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import time
from pathlib import Path

from utils.runtime_paths import PATHS


class DeveloperAccess:
    ITERATIONS = 310_000
    TOKEN_TTL = 30 * 60

    def __init__(self, path: Path | None = None):
        self.path = path or PATHS.data_dir / "developer" / "access.json"
        self._tokens: dict[str, float] = {}
        self._failures: list[float] = []

    @property
    def configured(self) -> bool:
        return self.path.is_file()

    def setup(self, password: str) -> str:
        if self.configured:
            raise ValueError("开发者密码已经设置")
        self._validate_password(password)
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, self.ITERATIONS)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="access", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({
                    "algorithm": "pbkdf2-sha256", "iterations": self.ITERATIONS,
                    "salt": base64.b64encode(salt).decode(),
                    "digest": base64.b64encode(digest).decode(),
                }, handle)
                handle.flush(); os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name): os.unlink(temp_name)
        return self._issue_token()

    def unlock(self, password: str) -> str:
        now = time.monotonic()
        self._failures = [stamp for stamp in self._failures if now - stamp < 60]
        if len(self._failures) >= 5:
            raise PermissionError("尝试次数过多，请稍后再试")
        if not self.configured:
            raise ValueError("尚未设置开发者密码")
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            salt = base64.b64decode(data["salt"])
            expected = base64.b64decode(data["digest"])
            actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(data["iterations"]))
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise ValueError("开发者凭据文件损坏") from exc
        if not hmac.compare_digest(actual, expected):
            self._failures.append(now)
            raise PermissionError("密码错误")
        self._failures.clear()
        return self._issue_token()

    def require(self, token: str) -> None:
        now = time.monotonic()
        expires = self._tokens.get(token, 0)
        if not token or expires <= now:
            self._tokens.pop(token, None)
            raise PermissionError("开发者模式未解锁或已过期")

    def lock(self, token: str) -> None:
        self._tokens.pop(token, None)

    def _issue_token(self) -> str:
        token = secrets.token_urlsafe(32)
        self._tokens[token] = time.monotonic() + self.TOKEN_TTL
        return token

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password) < 8:
            raise ValueError("密码至少需要 8 个字符")


developer_access = DeveloperAccess()
