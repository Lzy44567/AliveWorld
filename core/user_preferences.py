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
from typing import Any

import yaml

from utils.file_io import DATA_DIR


PREFERENCE_DIR = os.path.join(DATA_DIR, "preferences")
PREFERENCE_FILE = os.path.join(PREFERENCE_DIR, "user_preferences.yml")
VALID_CATEGORIES = {"narrative", "character", "relationship", "visual", "content", "boundary", "other"}
VALID_POLARITIES = {"prefer", "avoid"}
VALID_STATUSES = {"candidate", "active", "disabled"}


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

    def load(self) -> dict[str, Any]:
        try:
            with open(self.path, "r", encoding="utf-8") as file:
                data = yaml.safe_load(file) or {}
        except (FileNotFoundError, OSError, yaml.YAMLError):
            data = {}
        preferences = data.get("preferences", [])
        return {"version": 1, "preferences": preferences if isinstance(preferences, list) else []}

    def save(self, profile: dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        payload = {"version": 1, "preferences": list(profile.get("preferences", []))}
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
        profile = self.load()
        changed_ids: list[str] = []
        retained: list[dict[str, Any]] = []
        for item in profile["preferences"]:
            old_evidence = list(item.get("evidence", []))
            evidence = [
                entry for entry in old_evidence
                if not (entry.get("save_name") == save_name and int(entry.get("turn_id", -1)) == int(turn_id))
            ]
            if len(evidence) == len(old_evidence):
                retained.append(item)
                continue
            changed_ids.append(str(item.get("id", "")))
            if not evidence and not item.get("manual_override"):
                continue
            item["evidence"] = evidence
            item["evidence_count"] = len(evidence)
            if evidence:
                item["confidence"] = max(_confidence(entry.get("confidence")) for entry in evidence)
            if not item.get("manual_override") and item.get("status") != "disabled":
                explicit_active = any(
                    entry.get("explicit") and _confidence(entry.get("confidence")) >= 0.72
                    for entry in evidence
                )
                item["status"] = "active" if explicit_active or (
                    len(evidence) >= 2 and _confidence(item.get("confidence")) >= 0.65
                ) else "candidate"
            item["updated_at"] = _now()
            retained.append(item)
        if changed_ids:
            profile["preferences"] = retained
            self.save(profile)
        return changed_ids

    def delete(self, preference_id: str) -> bool:
        profile = self.load()
        before = len(profile["preferences"])
        profile["preferences"] = [entry for entry in profile["preferences"] if entry.get("id") != preference_id]
        if len(profile["preferences"]) == before:
            return False
        self.save(profile)
        return True

    def context(self, *, limit: int = 20, character_limit: int = 2400) -> str:
        active = [entry for entry in self.load()["preferences"] if entry.get("status") == "active"]
        active.sort(key=lambda entry: (entry.get("category", ""), -float(entry.get("confidence", 0))))
        lines = []
        for item in active[:limit]:
            verb = "偏好" if item.get("polarity") == "prefer" else "回避"
            lines.append(f"- [{item.get('id')}] {verb}：{item.get('statement')}（{item.get('category', 'other')}）")
        return "\n".join(lines)[:character_limit]
