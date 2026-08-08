"""Persistent per-workflow configuration without mutating imported JSON."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from utils.file_io import DATA_DIR


PROFILE_DIR = Path(DATA_DIR) / "image_workflow_profiles"
OVERRIDABLE_KEYS = {"checkpoint", "width", "height", "batch_size", "seed", "steps", "cfg"}


def compose_prompt(*parts: Any) -> str:
    """Join workflow base, AI scene, and player supplement in stable order."""
    return ", ".join(str(part).strip(" ,\n") for part in parts if str(part or "").strip(" ,\n"))


@dataclass
class WorkflowProfile:
    workflow_id: str
    workflow_fingerprint: str
    allow_overrides: bool = False
    overrides: dict[str, Any] = field(default_factory=dict)
    mapping_overrides: dict[str, list[str]] = field(default_factory=dict)
    player_positive: str = ""
    player_negative: str = ""

    @classmethod
    def from_dict(cls, workflow_id: str, fingerprint: str, data: dict[str, Any] | None) -> "WorkflowProfile":
        data = data if isinstance(data, dict) else {}
        overrides = {
            str(key): value for key, value in dict(data.get("overrides") or {}).items()
            if str(key) in OVERRIDABLE_KEYS
        }
        for key in list(overrides):
            try:
                if key in {"width", "height", "batch_size", "seed", "steps"}:
                    overrides[key] = int(overrides[key])
                elif key == "cfg":
                    overrides[key] = float(overrides[key])
            except (TypeError, ValueError):
                overrides.pop(key, None)
        mapping_overrides = {
            str(key): [str(value[0]), str(value[1])]
            for key, value in dict(data.get("mapping_overrides") or {}).items()
            if isinstance(value, list) and len(value) == 2
        }
        return cls(
            workflow_id=workflow_id,
            workflow_fingerprint=str(data.get("workflow_fingerprint", fingerprint)),
            allow_overrides=bool(data.get("allow_overrides", False)),
            overrides=overrides,
            mapping_overrides=mapping_overrides,
            player_positive=str(data.get("player_positive", "")).strip(),
            player_negative=str(data.get("player_negative", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorkflowProfileRepository:
    def __init__(self, root: str | Path = PROFILE_DIR):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, workflow_id: str) -> Path:
        safe = "".join(char for char in str(workflow_id) if char.isalnum() or char in "_-")
        if not safe:
            raise ValueError("工作流 ID 无效")
        return self.root / f"{safe}.json"

    def get(self, workflow_id: str, fingerprint: str) -> WorkflowProfile:
        path = self._path(workflow_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            data = {}
        profile = WorkflowProfile.from_dict(workflow_id, fingerprint, data)
        # Keep user supplements, but stale overrides must not target a changed graph.
        if profile.workflow_fingerprint != fingerprint:
            profile.workflow_fingerprint = fingerprint
            profile.allow_overrides = False
            profile.overrides = {}
            profile.mapping_overrides = {}
        return profile

    def save(self, workflow_id: str, fingerprint: str, data: dict[str, Any]) -> WorkflowProfile:
        profile = WorkflowProfile.from_dict(workflow_id, fingerprint, data)
        path = self._path(workflow_id)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
        return profile

    def reset(self, workflow_id: str, fingerprint: str) -> WorkflowProfile:
        path = self._path(workflow_id)
        if path.is_file():
            path.unlink()
        return WorkflowProfile(workflow_id=workflow_id, workflow_fingerprint=fingerprint)
