"""Application service for package previews, story materialization, and safe removal."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from core.world_packages.archive import WorldPackageImporter
from core.world_packages.identity import asset_id_from_data
from core.world_packages.models import InstallRecord, PackageFormatError, WorldPackageManifest


STORY_ASSET_TYPES = frozenset({"worldbooks", "characters", "styles", "entities"})


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _version_key(value: str) -> tuple[tuple[int, Any], ...]:
    return tuple((0, int(part)) if part.isdigit() else (1, part.casefold()) for part in re.split(r"[._+-]", value))


@dataclass(frozen=True)
class StoryStarter:
    world_premise: str
    opening: str
    story_settings: dict[str, Any]
    package_name: str


class WorldPackageService:
    def __init__(self, world_packages_root: str | Path, data_root: str | Path):
        self.root = Path(world_packages_root)
        self.data_root = Path(data_root)
        self.importer = WorldPackageImporter(self.root)

    def list_packages(self) -> list[dict[str, Any]]:
        return [self.package_detail(item.package_id, item.version) for item in self.importer.ledger.list()]

    def package_detail(self, package_id: str, version: str) -> dict[str, Any]:
        record = self.importer.ledger.find(package_id, version)
        if record is None:
            raise PackageFormatError("世界包尚未安装")
        manifest = self._manifest(record)
        modified, missing = self._changes(record)
        return {
            **manifest.to_dict(),
            "installed_at": record.installed_at,
            "modified_asset_ids": modified,
            "missing_asset_ids": missing,
            "healthy": not modified and not missing,
        }

    def preview_archive(self, archive_path: str | Path) -> dict[str, Any]:
        manifest = self.importer.inspect(archive_path)
        installed = [item for item in self.importer.ledger.list() if item.package_id == manifest.package_id]
        same = next((item for item in installed if item.version == manifest.version), None)
        if same:
            status = "same" if same.package_sha256 == _hash(Path(archive_path)) else "version_collision"
        elif not installed:
            status = "new"
        else:
            newest = max(installed, key=lambda item: _version_key(item.version))
            status = "update" if _version_key(manifest.version) > _version_key(newest.version) else "downgrade"
        known_assets = {
            asset["asset_id"]: asset
            for item in installed
            for asset in item.assets
        }
        conflicts = []
        for item in self.importer.ledger.list():
            if item.package_id == manifest.package_id:
                continue
            other = self._manifest(item)
            if other.name.casefold() == manifest.name.casefold():
                conflicts.append({
                    "package_id": item.package_id,
                    "name": other.name,
                    "kind": "package_name",
                    "message": "已有不同来源的同名世界包；两者会并存，不会覆盖。",
                })
        for asset in manifest.assets:
            previous = known_assets.get(asset.asset_id)
            if previous and previous["original_hash"] != asset.sha256:
                conflicts.append({"asset_id": asset.asset_id, "name": asset.name, "kind": "asset_update"})
        return {"status": status, "manifest": manifest.to_dict(), "conflicts": conflicts}

    def materialize_story(self, package_id: str, version: str, save_dir: str | Path) -> StoryStarter:
        record = self.importer.ledger.find(package_id, version)
        if record is None:
            raise PackageFormatError("世界包尚未安装")
        manifest = self._manifest(record)
        package_dir = (self.root / PurePosixPath(record.manifest_path)).parent
        by_id = {item.asset_id: item for item in manifest.assets}
        starter = {
            "world_premise": manifest.description,
            "opening": f"【{manifest.name}】\n世界已经准备就绪。描述你的第一步行动。",
            "story_settings": dict(manifest.recommended_settings),
        }
        starter_id = manifest.entrypoints.get("starter")
        if starter_id:
            starter_record = by_id.get(str(starter_id))
            if not starter_record or starter_record.asset_type != "starter":
                raise PackageFormatError("世界包起点引用无效")
            try:
                loaded = json.loads((package_dir / PurePosixPath(starter_record.path)).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise PackageFormatError("世界包故事起点无法读取") from exc
            if not isinstance(loaded, dict):
                raise PackageFormatError("世界包故事起点格式无效")
            for key in starter:
                if key in loaded:
                    starter[key] = loaded[key]
        if not isinstance(starter["story_settings"], dict):
            raise PackageFormatError("世界包推荐设置格式无效")

        destination_root = Path(save_dir)
        copied: list[Path] = []
        try:
            for asset in manifest.assets:
                if asset.optional or asset.asset_type not in STORY_ASSET_TYPES:
                    continue
                source = package_dir / PurePosixPath(asset.path)
                if not source.is_file() or _hash(source) != asset.sha256:
                    raise PackageFormatError(f"世界包资产已丢失或被修改：{asset.name}")
                destination = destination_root / asset.asset_type / Path(asset.path).name
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    raise PackageFormatError(f"故事目录中已存在同名包资产：{asset.name}")
                shutil.copy2(source, destination)
                copied.append(destination)
            provenance = destination_root / "world_package.json"
            provenance.write_text(json.dumps({
                "package_id": manifest.package_id,
                "version": manifest.version,
                "name": manifest.name,
                "asset_ids": [item.asset_id for item in manifest.assets if not item.optional],
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            copied.append(provenance)
        except Exception:
            for path in reversed(copied):
                path.unlink(missing_ok=True)
            raise
        return StoryStarter(
            world_premise=str(starter["world_premise"] or ""),
            opening=str(starter["opening"] or "").strip(),
            story_settings=dict(starter["story_settings"]),
            package_name=manifest.name,
        )

    def uninstall(self, package_id: str, version: str, *, mode: str = "safe", confirmed: bool = False) -> dict[str, Any]:
        if mode not in {"safe", "record_only", "purge"}:
            raise PackageFormatError("未知的卸载方式")
        if mode == "purge" and not confirmed:
            raise PackageFormatError("彻底移除前需要明确确认")
        record = self.importer.ledger.find(package_id, version)
        if record is None:
            raise PackageFormatError("世界包尚未安装")
        package_dir = (self.root / PurePosixPath(record.manifest_path)).parent
        modified, missing = self._changes(record)
        preserved: list[str] = []
        if mode == "safe":
            manifest = self._manifest(record)
            by_id = {item.asset_id: item for item in manifest.assets}
            for asset_id in modified:
                asset = by_id.get(asset_id)
                if not asset:
                    continue
                source = package_dir / PurePosixPath(asset.path)
                if source.is_file():
                    preserved.append(self._preserve_personal(asset.asset_type, asset.name, source, asset_id))

        recovery = self.root / "uninstall_records"
        recovery.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        audit = recovery / f"{package_id}-{version}-{stamp}.json"
        audit.write_text(json.dumps({
            "removed_at": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "record": record.to_dict(),
            "modified_asset_ids": modified,
            "missing_asset_ids": missing,
            "preserved_paths": preserved,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        moved_target: Path | None = None
        if mode in {"safe", "purge"} and package_dir.exists():
            trash = self.root / "uninstall_backups" / package_id
            trash.mkdir(parents=True, exist_ok=True)
            moved_target = trash / f"{version}-{stamp}-{uuid.uuid4().hex[:8]}"
            shutil.move(str(package_dir), moved_target)
        try:
            self.importer.ledger.remove(package_id, version)
        except Exception:
            if moved_target and moved_target.exists() and not package_dir.exists():
                package_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(moved_target), package_dir)
            raise
        if mode == "purge" and moved_target and moved_target.exists():
            shutil.rmtree(moved_target)
        return {"status": "removed", "mode": mode, "preserved_paths": preserved, "recovery_record": str(audit)}

    def _manifest(self, record: InstallRecord) -> WorldPackageManifest:
        path = self.root / PurePosixPath(record.manifest_path)
        try:
            return WorldPackageManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            raise PackageFormatError("已安装世界包的 manifest 损坏") from exc

    def _changes(self, record: InstallRecord) -> tuple[list[str], list[str]]:
        modified, missing = [], []
        for asset in record.assets:
            path = self.root / PurePosixPath(asset["path"])
            if not path.is_file():
                missing.append(asset["asset_id"])
            elif _hash(path) != asset["original_hash"]:
                modified.append(asset["asset_id"])
        return modified, missing

    def _preserve_personal(self, asset_type: str, name: str, source: Path, asset_id: str) -> str:
        if asset_type in STORY_ASSET_TYPES:
            destination_dir = self.data_root / asset_type
        elif asset_type == "workflows":
            destination_dir = self.data_root / "image_workflows" / "preserved"
        else:
            destination_dir = self.data_root / "world_packages" / "preserved" / asset_type
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / source.name
        if destination.exists():
            destination = destination_dir / f"{asset_id}{source.suffix}"
        if source.suffix.casefold() in {".yml", ".yaml"}:
            try:
                data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                data = None
            if isinstance(data, dict):
                existing_names = set()
                for candidate in destination_dir.glob("*.yml"):
                    try:
                        candidate_data = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
                    except (OSError, yaml.YAMLError):
                        continue
                    if asset_id_from_data(candidate_data) == asset_id:
                        return str(candidate)
                    existing_names.add(str(candidate_data.get("name", "")).strip().casefold())
                if str(data.get("name", "")).strip().casefold() in existing_names:
                    data["name"] = f"{name}（世界包保留）"
                temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
                temporary.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
                os.replace(temporary, destination)
                return str(destination)
        shutil.copy2(source, destination)
        return str(destination)
