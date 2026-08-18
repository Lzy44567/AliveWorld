"""Application service for previewing and committing external assets."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import yaml

from core.asset_lifecycle import filename_for_asset, normalize_asset_name
from core.worldbook import save_worldbook_atomic

from .adapters import parse_external_payload
from .models import ExternalFormatError, ImportPreview


class ExternalAssetImportService:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)

    def inspect(self, payload: bytes, filename: str, kind: str = "auto") -> ImportPreview:
        return parse_external_payload(payload, filename, kind)

    def commit(self, payload: bytes, filename: str, kind: str, requested_name: str = "") -> dict:
        preview = self.inspect(payload, filename, kind)
        try:
            name = normalize_asset_name(requested_name or preview.suggested_name)
            filename_value = filename_for_asset(name)
        except Exception as exc:
            raise ExternalFormatError(str(exc)) from exc
        directory = self.data_dir / preview.asset_type
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / filename_value
        if target.exists() or self._name_exists(directory, name):
            raise ExternalFormatError(f"已存在同名资产“{name}”，请修改导入名称")

        asset = dict(preview.mapped_asset)
        asset["name"] = name
        portrait_path: Path | None = None
        if preview.portrait_bytes is not None and preview.asset_type == "characters":
            portraits = directory / "_portraits"
            portraits.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256(preview.portrait_bytes).hexdigest()[:12]
            portrait_path = portraits / f"imported_{digest}.png"
            if not portrait_path.exists():
                portrait_path.write_bytes(preview.portrait_bytes)
            asset["portrait"] = {"scope": "global", "path": portrait_path.name, "source": "external_character_card"}
        try:
            if preview.asset_type == "worldbooks":
                save_worldbook_atomic(target, asset)
            else:
                temporary = target.with_name(f".{target.name}.tmp")
                temporary.write_text(yaml.safe_dump(asset, allow_unicode=True, sort_keys=False), encoding="utf-8")
                os.replace(temporary, target)
        except Exception:
            if portrait_path is not None and not self._portrait_referenced(directory, portrait_path.name):
                portrait_path.unlink(missing_ok=True)
            raise
        return {
            "status": "imported",
            "asset_type": preview.asset_type,
            "name": name,
            "path": str(target),
            "preview": preview.to_dict(),
        }

    @staticmethod
    def _name_exists(directory: Path, name: str) -> bool:
        for path in directory.glob("*.yml"):
            try:
                value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            if isinstance(value, dict) and str(value.get("name", "")).strip() == name:
                return True
        return False

    @staticmethod
    def _portrait_referenced(directory: Path, filename: str) -> bool:
        for path in directory.glob("*.yml"):
            try:
                value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            if str((value.get("portrait") or {}).get("path", "")) == filename:
                return True
        return False
