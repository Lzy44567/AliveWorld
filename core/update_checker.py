"""Read-only update discovery against the official AliveWorld GitHub releases."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from utils.version import APP_VERSION


RELEASE_SOURCES = (
    {
        "name": "stable-public-release",
        "api": "https://api.github.com/repos/Lzy44567/AliveWorld/releases?per_page=20",
        "page": "https://github.com/Lzy44567/AliveWorld/releases",
    },
    {
        "name": "temporary-release-staging",
        "api": "https://api.github.com/repos/Lzy44567/AliveWorld-Releases/releases?per_page=20",
        "page": "https://github.com/Lzy44567/AliveWorld-Releases/releases",
    },
)
RELEASES_PAGE = RELEASE_SOURCES[0]["page"]
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
    release = None
    release_source = None
    reachable_source = None
    errors: list[Exception] = []
    for source in RELEASE_SOURCES:
        request = Request(
            source["api"],
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"AliveWorld/{current_version}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                releases = json.loads(response.read().decode("utf-8"))
            if not isinstance(releases, list):
                raise ValueError("release payload is not a list")
            reachable_source = source
            release = select_release(
                releases,
                current_version=current_version,
                include_prerelease=include_prerelease,
            )
            if release is not None:
                release_source = source
                break
        except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(exc)

    if release is None:
        if reachable_source is None:
            if any(isinstance(exc, HTTPError) and exc.code in {403, 429} for exc in errors):
                raise UpdateCheckError("GitHub 检查次数暂时受限，请稍后重试。")
            raise UpdateCheckError("暂时无法连接 GitHub；这不会影响游戏。")
        return {
            "current_version": current_version,
            "latest_version": None,
            "update_available": False,
            "releases_url": RELEASES_PAGE,
            "message": "官方仓库暂时没有可用 Release。",
        }

    latest_version = str(release.get("tag_name") or "").removeprefix("v")
    assets = []
    for asset in release.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "").strip()
        url = str(asset.get("browser_download_url") or "").strip()
        if not name or not url.startswith("https://github.com/"):
            continue
        assets.append({
            "name": name,
            "url": url,
            "size": max(0, int(asset.get("size") or 0)),
            "digest": str(asset.get("digest") or "").strip(),
        })
    return {
        "current_version": current_version,
        "latest_version": latest_version,
        "update_available": is_newer(latest_version, current_version),
        "title": str(release.get("name") or release.get("tag_name") or latest_version),
        "notes": str(release.get("body") or "").strip()[:4000],
        "published_at": release.get("published_at"),
        "prerelease": bool(release.get("prerelease")),
        "release_url": str(release.get("html_url") or release_source["page"]),
        "releases_url": release_source["page"],
        "release_source": release_source["name"],
        "assets": assets,
    }
