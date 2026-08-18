"""Validation for deterministic initial state carried by a world package."""

from __future__ import annotations

from typing import Any

from core.world_packages.models import PackageFormatError


ALLOWED_COLORS = {"red", "pink", "orange", "amber", "emerald", "cyan", "indigo", "purple", "slate"}
MAX_ITEMS_PER_GROUP = 32


def _label(value: Any) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 40:
        raise PackageFormatError("世界包初始状态名称无效")
    return text


def _text(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) > 500:
        raise PackageFormatError("世界包初始状态内容过长")
    return text


def _number(value: Any, *, field: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PackageFormatError(f"世界包初始状态 {field} 必须是数字")
    if not -1_000_000 <= value <= 1_000_000:
        raise PackageFormatError(f"世界包初始状态 {field} 超出范围")
    return value


def _limited_mapping(raw: Any, *, group: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict) or len(raw) > MAX_ITEMS_PER_GROUP:
        raise PackageFormatError(f"世界包初始状态 {group} 格式无效")
    return raw


def normalize_initial_state(raw: Any) -> dict[str, Any]:
    if raw in (None, {}):
        return {}
    if not isinstance(raw, dict):
        raise PackageFormatError("世界包初始状态必须是对象")
    if set(raw) - {"properties", "bars", "buffs", "npcs"}:
        raise PackageFormatError("世界包初始状态包含未知分组")

    properties = {
        _label(name): _text(value)
        for name, value in _limited_mapping(raw.get("properties"), group="properties").items()
    }
    npcs = {
        _label(name): _text(value)
        for name, value in _limited_mapping(raw.get("npcs"), group="npcs").items()
    }

    bars: dict[str, dict[str, Any]] = {}
    for name, value in _limited_mapping(raw.get("bars"), group="bars").items():
        if not isinstance(value, dict):
            raise PackageFormatError("世界包初始状态条格式无效")
        maximum = _number(value.get("max", 100), field="max")
        current = _number(value.get("current", 0), field="current")
        if maximum <= 0:
            raise PackageFormatError("世界包初始状态条上限必须大于零")
        color = str(value.get("color", "indigo")).strip().lower()
        if color not in ALLOWED_COLORS:
            raise PackageFormatError("世界包初始状态条颜色无效")
        bars[_label(name)] = {
            "current": max(0, min(current, maximum)),
            "max": maximum,
            "change": 0,
            "color": color,
        }

    buffs: dict[str, dict[str, Any]] = {}
    for name, value in _limited_mapping(raw.get("buffs"), group="buffs").items():
        if not isinstance(value, dict):
            raise PackageFormatError("世界包初始效果格式无效")
        duration = value.get("duration", -1)
        if isinstance(duration, bool) or not isinstance(duration, int) or duration < -1 or duration > 100_000:
            raise PackageFormatError("世界包初始效果持续时间无效")
        buffs[_label(name)] = {
            "description": _text(value.get("description", "")),
            "duration": duration,
        }

    return {"properties": properties, "bars": bars, "buffs": buffs, "npcs": npcs}
