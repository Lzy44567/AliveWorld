"""Persistent, evidence-backed user preference profile.

The profile is global user data. Story turns only contribute observations; they
never replace the profile wholesale. This keeps preference learning reversible
and prevents a single role-play choice from becoming a permanent preference.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import os
import re
import threading
from typing import Any

import yaml

from utils.file_io import DATA_DIR


PREFERENCE_DIR = os.path.join(DATA_DIR, "preferences")
PREFERENCE_FILE = os.path.join(PREFERENCE_DIR, "user_preferences.yml")
VALID_CATEGORIES = {
    "story", "adult", "action", "character", "relationship", "visual", "boundary", "other",
    # v1.5-dev.1 compatibility
    "narrative", "content",
}
VALID_POLARITIES = {"prefer", "avoid"}
VALID_STATUSES = {"candidate", "active", "disabled"}
_path_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def _path_lock(path: str) -> threading.RLock:
    key = os.path.abspath(path)
    with _locks_guard:
        return _path_locks.setdefault(key, threading.RLock())


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _clean_text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _fingerprint(category: str, polarity: str, statement: str) -> str:
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "", statement.casefold())
    raw = f"{category}|{polarity}|{normalized}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:12]


class UserPreferenceRepository:
    def __init__(self, path: str = PREFERENCE_FILE):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._lock = _path_lock(path)

    def load(self) -> dict[str, Any]:
        try:
            with open(self.path, "r", encoding="utf-8") as file:
                data = yaml.safe_load(file) or {}
        except (FileNotFoundError, OSError, yaml.YAMLError):
            data = {}
        preferences = data.get("preferences", [])
        evidence = data.get("evidence", [])
        analysis = data.get("analysis", {})
        return {
            "version": 2,
            "preferences": preferences if isinstance(preferences, list) else [],
            "evidence": evidence if isinstance(evidence, list) else [],
            "analysis": analysis if isinstance(analysis, dict) else {},
        }

    def save(self, profile: dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        payload = {
            "version": 2,
            "preferences": list(profile.get("preferences", [])),
            "evidence": list(profile.get("evidence", [])),
            "analysis": dict(profile.get("analysis", {})),
        }
        temp_path = self.path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as file:
            yaml.safe_dump(payload, file, allow_unicode=True, sort_keys=False)
        os.replace(temp_path, self.path)

    def export_state(self) -> dict[str, Any]:
        return deepcopy(self.load())

    def restore_state(self, state: dict[str, Any]) -> None:
        self.save(deepcopy(state or {"version": 1, "preferences": []}))

    def observe(
        self,
        observations: Any,
        *,
        save_name: str,
        turn_id: int,
        player_action: str,
    ) -> list[dict[str, Any]]:
        if not isinstance(observations, list):
            return []
        profile = self.load()
        preferences = profile["preferences"]
        changed: list[dict[str, Any]] = []

        for raw in observations[:3]:
            if not isinstance(raw, dict):
                continue
            statement = _clean_text(raw.get("statement"), 180)
            evidence = _clean_text(raw.get("evidence"), 240)
            category = str(raw.get("category", "other")).strip().lower()
            polarity = str(raw.get("polarity", "prefer")).strip().lower()
            confidence = _confidence(raw.get("confidence"))
            explicit = bool(raw.get("explicit", False))
            if not statement or not evidence or confidence < 0.55:
                continue
            if category not in VALID_CATEGORIES:
                category = "other"
            if polarity not in VALID_POLARITIES:
                polarity = "prefer"

            target_id = _clean_text(raw.get("target_id"), 80)
            item = next((entry for entry in preferences if target_id and entry.get("id") == target_id), None)
            fingerprint = _fingerprint(category, polarity, statement)
            if item is None:
                item = next((entry for entry in preferences if entry.get("fingerprint") == fingerprint), None)

            evidence_item = {
                "save_name": _clean_text(save_name, 100),
                "turn_id": int(turn_id),
                "player_action": _clean_text(player_action, 240),
                "basis": evidence,
                "explicit": explicit,
                "confidence": confidence,
                "created_at": _now(),
            }
            if item is None:
                item = {
                    "id": f"preference_{fingerprint}",
                    "fingerprint": fingerprint,
                    "category": category,
                    "polarity": polarity,
                    "statement": statement,
                    "status": "candidate",
                    "confidence": confidence,
                    "evidence_count": 0,
                    "evidence": [],
                    "created_at": _now(),
                    "updated_at": _now(),
                }
                preferences.append(item)

            duplicate = any(
                entry.get("save_name") == evidence_item["save_name"] and entry.get("turn_id") == evidence_item["turn_id"]
                for entry in item.get("evidence", [])
            )
            if duplicate:
                continue
            item.setdefault("evidence", []).append(evidence_item)
            item["evidence"] = item["evidence"][-8:]
            item["evidence_count"] = int(item.get("evidence_count", 0)) + 1
            item["confidence"] = round(max(_confidence(item.get("confidence")), confidence), 3)
            item["updated_at"] = _now()
            if item.get("status") != "disabled" and (
                (explicit and confidence >= 0.72)
                or (item["evidence_count"] >= 2 and item["confidence"] >= 0.65)
            ):
                item["status"] = "active"
            changed.append(deepcopy(item))

        if changed:
            profile["preferences"] = preferences[-120:]
            self.save(profile)
        return changed

    def declare(
        self, statement: str, *, save_name: str = "", category: str = "other",
        polarity: str = "prefer", sensitive: bool = False,
    ) -> dict[str, Any] | None:
        """Store an out-of-character declaration as a strong prior, not an absolute truth."""
        statement = _clean_text(statement, 400)
        if not statement:
            return None
        category = category if category in VALID_CATEGORIES else "other"
        polarity = polarity if polarity in VALID_POLARITIES else "prefer"
        with self._lock:
            profile = self.load()
            fingerprint = _fingerprint(category, polarity, statement)
            item = next((entry for entry in profile["preferences"] if entry.get("fingerprint") == fingerprint), None)
            if item is None:
                item = {
                    "id": f"preference_{fingerprint}", "fingerprint": fingerprint,
                    "category": category, "polarity": polarity, "statement": statement,
                    "status": "active", "confidence": 0.75, "posterior": 0.75,
                    "source_type": "declared", "sensitive": bool(sensitive),
                    "evidence_count": 1, "evidence": [], "manual_override": True,
                    "created_at": _now(), "updated_at": _now(),
                }
                profile["preferences"].append(item)
            else:
                item["status"] = "active"
                item["confidence"] = max(_confidence(item.get("confidence")), 0.75)
                item["posterior"] = max(_confidence(item.get("posterior")), 0.75)
                item["manual_override"] = True
                item["updated_at"] = _now()
            item.setdefault("declarations", []).append({
                "save_name": _clean_text(save_name, 100), "text": statement, "created_at": _now(),
            })
            item["declarations"] = item["declarations"][-8:]
            self.save(profile)
            return deepcopy(item)

    def record_evidence(self, evidence_items: Any, *, save_name: str, turn_id: int) -> list[dict[str, Any]]:
        """Append neutral behavioral evidence without turning it directly into a preference."""
        if not isinstance(evidence_items, list):
            return []
        added: list[dict[str, Any]] = []
        with self._lock:
            profile = self.load()
            known_ids = {str(item.get("id")) for item in profile["evidence"]}
            for raw in evidence_items[:3]:
                if not isinstance(raw, dict):
                    continue
                summary = _clean_text(raw.get("summary") or raw.get("evidence"), 300)
                context = _clean_text(raw.get("context"), 400)
                diagnosticity = str(raw.get("diagnosticity", "weak")).lower()
                signal_type = _clean_text(raw.get("signal_type"), 40) or "choice"
                if not summary or diagnosticity not in {"weak", "moderate", "strong"}:
                    continue
                raw_id = f"{save_name}|{turn_id}|{summary}".encode("utf-8")
                evidence_id = f"evidence_{hashlib.sha1(raw_id).hexdigest()[:12]}"
                if evidence_id in known_ids:
                    continue
                item = {
                    "id": evidence_id, "save_name": _clean_text(save_name, 100), "turn_id": int(turn_id),
                    "signal_type": signal_type, "summary": summary, "context": context,
                    "diagnosticity": diagnosticity, "sensitive": bool(raw.get("sensitive", False)),
                    "analyzed": False, "created_at": _now(),
                }
                profile["evidence"].append(item)
                known_ids.add(evidence_id)
                added.append(deepcopy(item))
            if added:
                profile["evidence"] = profile["evidence"][-300:]
                self.save(profile)
        return added

    def pending_evidence(self, *, include_sensitive: bool, limit: int = 24) -> list[dict[str, Any]]:
        evidence = [item for item in self.load()["evidence"] if not item.get("analyzed")]
        if not include_sensitive:
            evidence = [item for item in evidence if not item.get("sensitive")]
        return evidence[:limit]

    def recent_evidence(self, *, include_sensitive: bool, limit: int = 24) -> list[dict[str, Any]]:
        """Return recent evidence for explicit reconsideration passes."""
        evidence = self.load()["evidence"]
        if not include_sensitive:
            evidence = [item for item in evidence if not item.get("sensitive")]
        return evidence[-limit:]

    def analysis_snapshot(self) -> dict[str, Any]:
        profile = self.load()
        return {
            "preferences": [
                {key: item.get(key) for key in ("id", "statement", "category", "polarity", "status", "posterior")}
                for item in profile["preferences"][-60:]
            ],
            "analysis": deepcopy(profile.get("analysis", {})),
        }

    def apply_analysis(self, payload: dict[str, Any], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply ordinal AI assessments through deterministic Python odds updates."""
        from core.preference_analysis import update_probability

        evidence_by_id = {str(item.get("id")): item for item in evidence}
        changed: list[dict[str, Any]] = []
        with self._lock:
            profile = self.load()
            all_evidence_by_id = {str(item.get("id")): item for item in profile["evidence"]}
            for raw in payload.get("hypotheses", []) if isinstance(payload.get("hypotheses"), list) else []:
                if not isinstance(raw, dict):
                    continue
                statement = _clean_text(raw.get("statement"), 180)
                category = str(raw.get("category", "other")).lower()
                polarity = str(raw.get("polarity", "prefer")).lower()
                if not statement:
                    continue
                if category not in VALID_CATEGORIES:
                    category = "other"
                if polarity not in VALID_POLARITIES:
                    polarity = "prefer"
                target_id = _clean_text(raw.get("target_id"), 80)
                fingerprint = _fingerprint(category, polarity, statement)
                item = next((entry for entry in profile["preferences"] if target_id and entry.get("id") == target_id), None)
                if item is None:
                    item = next((entry for entry in profile["preferences"] if entry.get("fingerprint") == fingerprint), None)
                if item is None:
                    item = {
                        "id": f"preference_{fingerprint}", "fingerprint": fingerprint,
                        "category": category, "polarity": polarity, "statement": statement,
                        "status": "candidate", "confidence": 0.2, "posterior": 0.2,
                        "source_type": "inferred", "sensitive": bool(raw.get("sensitive", False)),
                        "evidence_count": 0, "evidence": [], "applied_evidence_ids": [],
                        "created_at": _now(), "updated_at": _now(),
                    }
                    profile["preferences"].append(item)
                probability = _confidence(item.get("posterior", item.get("confidence", 0.2))) or 0.2
                applied = set(str(value) for value in item.get("applied_evidence_ids", []))
                applied_before = set(applied)
                assessment_log = list(item.get("assessments", []))
                for assessment in raw.get("assessments", []) if isinstance(raw.get("assessments"), list) else []:
                    evidence_id = str(assessment.get("evidence_id", ""))
                    if evidence_id not in evidence_by_id or evidence_id in applied:
                        continue
                    direction = str(assessment.get("direction", "neutral")).lower()
                    strength = str(assessment.get("strength", "weak")).lower()
                    probability = update_probability(probability, direction, strength)
                    applied.add(evidence_id)
                    assessment_log.append({
                        "evidence_id": evidence_id, "direction": direction, "strength": strength,
                        "reason": _clean_text(assessment.get("reason"), 240), "created_at": _now(),
                    })
                if applied == applied_before:
                    continue
                item["posterior"] = round(probability, 4)
                item["confidence"] = item["posterior"]
                item["applied_evidence_ids"] = list(applied)[-60:]
                item["assessments"] = assessment_log[-60:]
                item["evidence_count"] = len(applied)
                stories = {all_evidence_by_id[eid].get("save_name") for eid in applied if eid in all_evidence_by_id}
                if not item.get("manual_override") and item.get("status") != "disabled":
                    item["status"] = "active" if probability >= 0.8 and len(stories) >= 2 else "candidate"
                item["updated_at"] = _now()
                changed.append(deepcopy(item))

            analyzed_ids = set(evidence_by_id)
            for item in profile["evidence"]:
                if str(item.get("id")) in analyzed_ids:
                    item["analyzed"] = True
            analysis = profile.setdefault("analysis", {})
            analysis["last_run_at"] = _now()
            analysis["coverage_note"] = _clean_text(payload.get("coverage_note"), 600)
            analysis["missing_possibilities"] = [
                _clean_text(value, 180) for value in payload.get("missing_possibilities", [])[:8]
                if _clean_text(value, 180)
            ] if isinstance(payload.get("missing_possibilities"), list) else []
            analysis["last_evidence_ids"] = list(analyzed_ids)
            self.save(profile)
        return changed

    def update(self, preference_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        profile = self.load()
        item = next((entry for entry in profile["preferences"] if entry.get("id") == preference_id), None)
        if item is None:
            return None
        if "statement" in updates:
            statement = _clean_text(updates.get("statement"), 180)
            if statement:
                item["statement"] = statement
        if updates.get("category") in VALID_CATEGORIES:
            item["category"] = updates["category"]
        if updates.get("polarity") in VALID_POLARITIES:
            item["polarity"] = updates["polarity"]
        if updates.get("status") in VALID_STATUSES:
            item["status"] = updates["status"]
        if any(key in updates for key in ("statement", "category", "polarity", "status")):
            item["manual_override"] = True
        item["updated_at"] = _now()
        self.save(profile)
        return deepcopy(item)

    def remove_turn_evidence(self, *, save_name: str, turn_id: int) -> list[str]:
        """Undo only evidence created by one story turn, without replacing global state."""
        from core.preference_analysis import update_probability

        with self._lock:
            profile = self.load()
            removed_behavior_ids = {
                str(entry.get("id")) for entry in profile["evidence"]
                if entry.get("save_name") == save_name and int(entry.get("turn_id", -1)) == int(turn_id)
            }
            profile["evidence"] = [entry for entry in profile["evidence"] if str(entry.get("id")) not in removed_behavior_ids]
            changed_ids: list[str] = []
            retained: list[dict[str, Any]] = []
            for item in profile["preferences"]:
                old_evidence = list(item.get("evidence", []))
                evidence = [
                    entry for entry in old_evidence
                    if not (entry.get("save_name") == save_name and int(entry.get("turn_id", -1)) == int(turn_id))
                ]
                assessments = [
                    entry for entry in item.get("assessments", [])
                    if str(entry.get("evidence_id")) not in removed_behavior_ids
                ]
                changed = len(evidence) != len(old_evidence) or len(assessments) != len(item.get("assessments", []))
                if not changed:
                    retained.append(item)
                    continue
                changed_ids.append(str(item.get("id", "")))
                item["evidence"] = evidence
                item["assessments"] = assessments
                item["applied_evidence_ids"] = [entry.get("evidence_id") for entry in assessments]
                if item.get("source_type") == "inferred":
                    probability = 0.2
                    for assessment in assessments:
                        probability = update_probability(
                            probability, str(assessment.get("direction", "neutral")), str(assessment.get("strength", "weak"))
                        )
                    item["posterior"] = round(probability, 4)
                    item["confidence"] = item["posterior"]
                    item["evidence_count"] = len(assessments)
                    if not assessments and not item.get("manual_override"):
                        continue
                    if not item.get("manual_override") and item.get("status") != "disabled":
                        item["status"] = "candidate"
                else:
                    item["evidence_count"] = len(evidence)
                    if evidence:
                        item["confidence"] = max(_confidence(entry.get("confidence")) for entry in evidence)
                    if not evidence and not item.get("manual_override"):
                        continue
                    if not item.get("manual_override") and item.get("status") != "disabled":
                        explicit_activation = any(
                            entry.get("explicit") and _confidence(entry.get("confidence")) >= 0.72
                            for entry in evidence
                        )
                        repeated_activation = len(evidence) >= 2 and _confidence(item.get("confidence")) >= 0.65
                        item["status"] = "active" if explicit_activation or repeated_activation else "candidate"
                item["updated_at"] = _now()
                retained.append(item)
            if changed_ids or removed_behavior_ids:
                profile["preferences"] = retained
                self.save(profile)
            return changed_ids + list(removed_behavior_ids)

    def delete(self, preference_id: str) -> bool:
        profile = self.load()
        before = len(profile["preferences"])
        profile["preferences"] = [entry for entry in profile["preferences"] if entry.get("id") != preference_id]
        if len(profile["preferences"]) == before:
            return False
        self.save(profile)
        return True

    def context(self, *, categories: set[str] | None = None, limit: int = 20, character_limit: int = 2400) -> str:
        active = [entry for entry in self.load()["preferences"] if entry.get("status") == "active"]
        if categories is not None:
            active = [entry for entry in active if entry.get("category", "other") in categories]
        active.sort(key=lambda entry: (entry.get("category", ""), -float(entry.get("confidence", 0))))
        lines = []
        for item in active[:limit]:
            verb = "偏好" if item.get("polarity") == "prefer" else "回避"
            lines.append(f"- [{item.get('id')}] {verb}：{item.get('statement')}（{item.get('category', 'other')}）")
        return "\n".join(lines)[:character_limit]
