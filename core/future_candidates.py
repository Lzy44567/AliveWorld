"""Validation and weighted selection for near-future candidates."""

from __future__ import annotations

import random
from typing import Any, Iterable


DEFAULT_WEIGHT = 50.0
MAX_WEIGHT = 1_000_000.0


def _clean_basis(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:8]


def _clean_weight(value: Any, *, eligible: bool) -> float:
    if not eligible:
        return 0.0
    try:
        weight = float(value)
    except (TypeError, ValueError):
        weight = DEFAULT_WEIGHT
    if weight <= 0:
        return 0.0
    return min(weight, MAX_WEIGHT)


def normalize_candidates(raw_candidates: Any) -> list[dict[str, Any]]:
    """Return safe candidates while retaining ineligible items for debug UI."""
    if not isinstance(raw_candidates, list):
        raw_candidates = []

    normalized = []
    for index, raw in enumerate(raw_candidates, start=1):
        if not isinstance(raw, dict):
            continue
        description = str(raw.get("description", "")).strip()
        if not description:
            continue
        eligible = raw.get("eligible", True) is not False
        normalized.append({
            "id": raw.get("id", index),
            "description": description,
            "eligible": eligible,
            "weight": _clean_weight(raw.get("weight", DEFAULT_WEIGHT), eligible=eligible),
            "basis": _clean_basis(raw.get("basis", [])),
        })

    if normalized and any(item["eligible"] and item["weight"] > 0 for item in normalized):
        return normalized

    return [{
        "id": 1,
        "description": "世界按当前事实与因果继续发展",
        "eligible": True,
        "weight": DEFAULT_WEIGHT,
        "basis": ["模型没有返回可进入随机池的有效候选"],
    }]


def choose_candidate(
    candidates: Iterable[dict[str, Any]],
    *,
    exclude_description: str = "",
) -> dict[str, Any]:
    """Choose from eligible positive-weight candidates, optionally avoiding one result."""
    pool = [item for item in candidates if item.get("eligible", True) and item.get("weight", 0) > 0]
    alternatives = [item for item in pool if item.get("description") != exclude_description]
    if alternatives:
        pool = alternatives
    if not pool:
        raise ValueError("没有可供抽取的动态未来候选")
    return random.choices(pool, weights=[item["weight"] for item in pool], k=1)[0]


def candidate_probability(candidate: dict[str, Any], candidates: Iterable[dict[str, Any]]) -> float:
    """Return normalized debug probability without changing stored relative weights."""
    pool = [item for item in candidates if item.get("eligible", True) and item.get("weight", 0) > 0]
    total = sum(float(item["weight"]) for item in pool)
    return float(candidate.get("weight", 0)) / total if total else 0.0
