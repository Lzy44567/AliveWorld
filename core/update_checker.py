"""Read-only update discovery against the official AliveWorld GitHub releases."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from utils.version import APP_VERSION


RELEASES_API = "https://api.github.com/repos/Lzy44567/AliveWorld/releases?per_page=20"
RELEASES_PAGE = "https://github.com/Lzy44567/AliveWorld/releases"
VERSION_RE = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<label>[0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)
PRERELEASE_RANK = {"dev": 0, "alpha": 1, "beta": 2, "rc": 3}


class UpdateCheckError(RuntimeError):
    """A readable, non-fatal update check failure."""


@dataclass(frozen=True)
class ParsedVersion:
    core: tuple[int, int, int]
    prerelease: tuple[tuple[int, int | str], ...] | None


def parse_version(value: str) -> ParsedVersion | None:
    match = VERSION_RE.match(str(value or "").strip())
    if not match:
        return None
    label = match.group("label")
    prerelease: tuple[tuple[int, int | str], ...] | None = None
    if label:
        parts: list[tuple[int, int | str]] = []
        for index, token in enumerate(label.lower().split(".")):
            if token.isdigit():
                parts.append((1, int(token)))
            elif index == 0 and token in PRERELEASE_RANK:
                parts.append((0, PRERELEASE_RANK[token]))
            else:
                parts.append((0, token))
        prerelease = tuple(parts)
    return ParsedVersion(
        core=(
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
        ),
        prerelease=prerelease,
    )


def is_newer(candidate: str, current: str) -> bool:
    candidate_version = parse_version(candidate)
    current_version = parse_version(current)
    if candidate_version is None or current_version is None:
        return False
    return _version_key(candidate_version) > _version_key(current_version)


def _version_key(version: ParsedVersion) -> tuple[Any, ...]:
    if version.prerelease is None:
        prerelease_key: tuple[Any, ...] = (1,)
    else:
        normalized = []
        for kind, value in version.prerelease:
            if isinstance(value, int):
                normalized.append((kind, value, ""))
            else:
                normalized.append((kind, -1, value))
        prerelease_key = (0, *normalized)
    return (*version.core, prerelease_key)


def select_release(
    releases: list[dict[str, Any]],
    *,
    current_version: str = APP_VERSION,
    include_prerelease: bool = True,
) -> dict[str, Any] | None:
    usable = []
    for release in releases:
        if release.get("draft"):
            continue
        if release.get("prerelease") and not include_prerelease:
            continue
        tag = str(release.get("tag_name") or "").strip()
        if parse_version(tag) is None:
            continue
        usable.append(release)
    if not usable:
        return None
    usable.sort(
        key=lambda item: _version_key(
            parse_version(str(item.get("tag_name") or ""))  # type: ignore[arg-type]
        ),
        reverse=True,
    )
    return usable[0]


def check_for_updates(
    *,
    current_version: str = APP_VERSION,
    include_prerelease: bool = True,
    timeout: float = 5.0,
) -> dict[str, Any]:
    request = Request(
        RELEASES_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"AliveWorld/{current_version}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            releases = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code in {403, 429}:
            raise UpdateCheckError("GitHub 检查次数暂时受限，请稍后重试。") from exc
        raise UpdateCheckError(f"GitHub 返回 HTTP {exc.code}。") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise UpdateCheckError("暂时无法连接 GitHub；这不会影响游戏。") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateCheckError("GitHub 返回了无法识别的版本数据。") from exc

    if not isinstance(releases, list):
        raise UpdateCheckError("GitHub 返回了无法识别的版本数据。")
    release = select_release(
        releases,
        current_version=current_version,
        include_prerelease=include_prerelease,
    )
    if release is None:
        return {
            "current_version": current_version,
            "latest_version": None,
            "update_available": False,
            "releases_url": RELEASES_PAGE,
            "message": "官方仓库暂时没有可用 Release。",
        }

    latest_version = str(release.get("tag_name") or "").removeprefix("v")
    return {
        "current_version": current_version,
        "latest_version": latest_version,
        "update_available": is_newer(latest_version, current_version),
        "title": str(release.get("name") or release.get("tag_name") or latest_version),
        "notes": str(release.get("body") or "").strip()[:4000],
        "published_at": release.get("published_at"),
        "prerelease": bool(release.get("prerelease")),
        "release_url": str(release.get("html_url") or RELEASES_PAGE),
        "releases_url": RELEASES_PAGE,
    }
