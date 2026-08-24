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


def _clean_fact_checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:16]:
        if not isinstance(item, dict):
            continue
        fact = str(item.get("fact", "")).strip()
        if not fact:
            continue
        result.append({
            "fact": fact[:500],
            "compatible": item.get("compatible") is True,
            "reason": str(item.get("reason", "")).strip()[:500],
        })
    return result


def normalize_candidates(raw_candidates: Any, *, required_facts: Any = None) -> list[dict[str, Any]]:
    """Return safe candidates while retaining ineligible items for debug UI."""
    if not isinstance(raw_candidates, list):
        raw_candidates = []
    facts = [str(item).strip() for item in (required_facts or []) if str(item).strip()][:12]

    normalized = []
    for index, raw in enumerate(raw_candidates, start=1):
        if not isinstance(raw, dict):
            continue
        description = str(raw.get("description", "")).strip()
        if not description:
            continue
        fact_checks = _clean_fact_checks(raw.get("fact_checks", []))
        checks_by_fact = {item["fact"]: item for item in fact_checks}
        facts_verified = not facts or all(
            checks_by_fact.get(fact, {}).get("compatible") is True for fact in facts
        )
        eligible = raw.get("eligible", True) is not False and facts_verified
        normalized.append({
            "id": raw.get("id", index),
            "description": description,
            "eligible": eligible,
            "weight": _clean_weight(raw.get("weight", DEFAULT_WEIGHT), eligible=eligible),
            "basis": _clean_basis(raw.get("basis", [])),
            "fact_checks": fact_checks,
        })

    if normalized and any(item["eligible"] and item["weight"] > 0 for item in normalized):
        return normalized

    return [{
        "id": 1,
        "description": "世界按当前事实与因果继续发展",
        "eligible": True,
        "weight": DEFAULT_WEIGHT,
        "basis": ["模型没有返回可进入随机池的有效候选"],
        "fact_checks": [{"fact": fact, "compatible": True, "reason": "安全回退保持既有事实"} for fact in facts],
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
