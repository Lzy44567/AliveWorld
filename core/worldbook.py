"""Worldbook domain normalization and retrieval boundaries."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Protocol


SYSTEM_TAGS = {
    "绝对规则": "世界客观规律或不可随意违反的规则；新增和修改需要谨慎确认。",
    "常驻": "只要世界书启用，该条目就进入世界上下文。",
    "传闻": "世界中的说法或认知，真实性尚未确认。",
    "玩家设定": "玩家在世界书创作界面明确建立的设定。",
    "AI推断": "由正文或世界书 AI 推导，仍应允许玩家检查。",
    "Overseer推断": "由暗流统筹发现的候选设定，不等同于客观事实。",
    "待确认": "尚未正式成为世界事实，不参与正文检索。",
    "待删除": "已自动停用、等待玩家确认删除的条目。",
}

AXIOM_PREFIX = re.compile(r"^\s*(?:(?:\d+|[一二三四五六七八九十]+)[.、．)]|[-*•])\s*")


def normalize_axioms(value: Any) -> list[str]:
    items = value.splitlines() if isinstance(value, str) else (value if isinstance(value, list) else [])
    return [cleaned for item in items if (cleaned := AXIOM_PREFIX.sub("", str(item).strip()).strip())]


def normalize_tags(value: Any) -> list[str]:
    if isinstance(value, str):
        value = re.split(r"[,，]", value)
    if not isinstance(value, list):
        return []
    result = []
    for tag in value:
        clean = str(tag).strip()
        if clean and clean not in result:
            result.append(clean)
    return result


def _entry_id(name: str, content: str) -> str:
    digest = hashlib.sha1(f"{name}\n{content}".encode("utf-8")).hexdigest()[:12]
    return f"entry_{digest}"


def normalize_entry(raw: Any) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    name = str(raw.get("name", "")).strip()
    content = str(raw.get("content", "")).strip()
    tags = normalize_tags(raw.get("tags", []))
    active = raw.get("is_active", True) is not False and "待删除" not in tags
    return {
        "id": str(raw.get("id") or _entry_id(name, content)),
        "name": name,
        "keys": str(raw.get("keys", "")).replace("，", ",").strip(),
        "content": content,
        "tags": tags,
        "is_active": active,
    }


def normalize_worldbook(raw: Any) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    normalized = dict(raw)
    normalized["name"] = str(raw.get("name", "")).strip()
    normalized["tags"] = normalize_tags(raw.get("tags", []))
    normalized["overview"] = str(raw.get("overview", raw.get("global_setting", ""))).strip()
    normalized["axioms"] = normalize_axioms(raw.get("axioms", []))
    normalized.pop("global_setting", None)
    normalized["entries"] = [normalize_entry(item) for item in raw.get("entries", []) if isinstance(item, dict)]
    return normalized


def save_worldbook_atomic(path: Path | str, book: dict[str, Any]) -> None:
    """Write a complete YAML file without exposing readers to partial content."""
    import yaml
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(yaml.safe_dump(normalize_worldbook(book), allow_unicode=True, sort_keys=False), encoding="utf-8")
    os.replace(temporary, target)


@dataclass(frozen=True)
class RetrievalHit:
    entry: dict[str, Any]
    score: float
    reasons: tuple[str, ...]


class SemanticRetriever(Protocol):
    def scores(self, query: str, entries: list[dict[str, Any]]) -> dict[str, float]: ...


class WorldbookRetriever:
    """Hybrid retrieval. A semantic provider can be added without changing callers."""

    def __init__(self, semantic: SemanticRetriever | None = None, budget_chars: int = 6000, semantic_threshold: float = 0.35):
        self.semantic = semantic
        self.budget_chars = budget_chars
        self.semantic_threshold = semantic_threshold

    def retrieve(self, entries: list[dict[str, Any]], query: str) -> tuple[list[RetrievalHit], list[RetrievalHit]]:
        semantic_scores = self.semantic.scores(query, entries) if self.semantic else {}
        candidates = []
        for raw in entries:
            entry = normalize_entry(raw)
            tags = set(entry["tags"])
            if not entry["is_active"] or "待确认" in tags or "待删除" in tags:
                continue
            reasons = []
            score = 0.0
            keys = [key.strip() for key in entry["keys"].split(",") if key.strip()]
            matched = [key for key in keys if key.casefold() in query.casefold()]
            if matched:
                score += 100.0
                reasons.append("关键词:" + "/".join(matched[:3]))
            if "常驻" in tags:
                score += 1000.0
                reasons.append("常驻")
            semantic_score = float(semantic_scores.get(entry["id"], 0.0))
            if semantic_score >= self.semantic_threshold:
                score += semantic_score * 100.0
                reasons.append(f"语义:{semantic_score:.3f}")
            if score > 0:
                candidates.append(RetrievalHit(entry, score, tuple(reasons)))

        candidates.sort(key=lambda hit: (-hit.score, hit.entry["name"]))
        selected, omitted = [], []
        used = 0
        for hit in candidates:
            cost = len(hit.entry["name"]) + len(hit.entry["content"])
            if selected and used + cost > self.budget_chars:
                omitted.append(hit)
                continue
            selected.append(hit)
            used += cost
        return selected, omitted
