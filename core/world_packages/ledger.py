"""Atomic installation ledger. It never infers ownership from display names."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from core.world_packages.models import InstallRecord, PackageFormatError


class InstallLedger:
    def __init__(self, world_packages_root: str | Path):
        self.root = Path(world_packages_root)
        self.path = self.root / "installations.json"

    def list(self) -> list[InstallRecord]:
        if not self.path.is_file():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PackageFormatError("世界包安装账本损坏") from exc
        if not isinstance(raw, dict) or raw.get("schema_version") != 1 or not isinstance(raw.get("packages"), list):
            raise PackageFormatError("世界包安装账本格式无效")
        return [InstallRecord.from_dict(item) for item in raw["packages"]]

    def find(self, package_id: str, version: str | None = None) -> InstallRecord | None:
        matches = [item for item in self.list() if item.package_id == package_id]
        if version is not None:
            matches = [item for item in matches if item.version == version]
        return matches[-1] if matches else None

    def upsert(self, record: InstallRecord) -> None:
        records = [
            item for item in self.list()
            if not (item.package_id == record.package_id and item.version == record.version)
        ]
        records.append(record)
        records.sort(key=lambda item: (item.package_id, item.version))
        payload = {"schema_version": 1, "packages": [item.to_dict() for item in records]}
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)
