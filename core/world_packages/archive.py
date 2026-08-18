"""Deterministic export and safe local installation of `.aliveworld` ZIP files."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import yaml

from core.world_packages.identity import ensure_yaml_asset_id
from core.world_packages.ledger import InstallLedger
from core.world_packages.models import (
    ASSET_TYPES,
    PACKAGE_EXTENSION,
    AssetRecord,
    InstallRecord,
    PackageFormatError,
    WorldPackageManifest,
    new_asset_id,
    validate_package_path,
)
from core.world_packages.privacy import PrivacyIssue, scan_asset


MAX_FILE_COUNT = 500
MAX_FILE_SIZE = 128 * 1024 * 1024
MAX_PACKAGE_SIZE = 512 * 1024 * 1024


@dataclass(frozen=True)
class AssetSource:
    asset_type: str
    path: Path
    name: str = ""
    asset_id: str = ""
    dependencies: tuple[str, ...] = ()
    optional: bool = False


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def _read_name(source: AssetSource, content: bytes) -> str:
    if source.name.strip():
        return source.name.strip()
    if source.path.suffix.casefold() in {".yml", ".yaml"}:
        try:
            raw = yaml.safe_load(content.decode("utf-8")) or {}
            if isinstance(raw, dict) and str(raw.get("name", "")).strip():
                return str(raw["name"]).strip()
        except (UnicodeDecodeError, yaml.YAMLError):
            pass
    return source.path.stem


def _asset_identifier(source: AssetSource) -> str:
    if source.asset_id:
        return source.asset_id
    if source.path.suffix.casefold() in {".yml", ".yaml"}:
        return ensure_yaml_asset_id(source.path)
    return new_asset_id()


class WorldPackageExporter:
    def export(
        self,
        target: str | Path,
        *,
        package: dict[str, Any],
        assets: Iterable[AssetSource],
    ) -> WorldPackageManifest:
        target_path = Path(target)
        if target_path.suffix.casefold() != PACKAGE_EXTENSION:
            target_path = target_path.with_suffix(PACKAGE_EXTENSION)
        source_items = list(assets)
        if not source_items:
            raise PackageFormatError("世界包至少需要一个资产")
        if len(source_items) > MAX_FILE_COUNT:
            raise PackageFormatError("世界包文件数量超过首版限制")

        prepared: list[tuple[AssetRecord, bytes]] = []
        privacy_issues: list[PrivacyIssue] = []
        seen_source_paths: set[Path] = set()
        for source in source_items:
            if source.asset_type not in ASSET_TYPES:
                raise PackageFormatError(f"不支持的资产类型：{source.asset_type}")
            original_path = Path(source.path)
            if original_path.is_symlink():
                raise PackageFormatError(f"世界包不能包含符号链接：{source.path}")
            path = original_path.resolve()
            if path in seen_source_paths:
                raise PackageFormatError("不能重复打包同一个源文件")
            seen_source_paths.add(path)
            if not path.is_file():
                raise PackageFormatError(f"资产不存在或不是普通文件：{source.path}")
            content = path.read_bytes()
            if len(content) > MAX_FILE_SIZE:
                raise PackageFormatError(f"资产超过单文件大小限制：{path.name}")
            source_issues = scan_asset(path.name, content)
            forbidden_parent = {part.casefold() for part in path.parts} & {
                "logs", "saves", "preferences", "workshops", "asset_workshops", "cache", "models"
            }
            if forbidden_parent:
                source_issues.append(PrivacyIssue("private_source", "源文件位于私人数据目录"))
            privacy_issues.extend(source_issues)
            if source_issues:
                continue
            asset_id = _asset_identifier(source)
            # ensure_yaml_asset_id may have added persistent metadata; package
            # the updated bytes so the imported card keeps the same identity.
            content = path.read_bytes()
            archive_path = f"{source.asset_type}/{asset_id}{path.suffix.lower()}"
            privacy_issues.extend(scan_asset(archive_path, content))
            prepared.append((AssetRecord(
                asset_id=asset_id,
                asset_type=source.asset_type,
                name=_read_name(source, content),
                path=archive_path,
                sha256=_sha256(content),
                size=len(content),
                dependencies=source.dependencies,
                optional=source.optional,
            ), content))
        if sum(record.size for record, _ in prepared) > MAX_PACKAGE_SIZE:
            raise PackageFormatError("世界包总大小超过首版限制")
        if privacy_issues:
            summary = "；".join(item.message for item in privacy_issues[:5])
            raise PackageFormatError(f"隐私扫描未通过：{summary}")

        manifest = WorldPackageManifest(assets=tuple(record for record, _ in prepared), **package)
        manifest_bytes = json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        manifest_issues = scan_asset("manifest.json", manifest_bytes)
        if manifest_issues:
            raise PackageFormatError(f"manifest 隐私扫描未通过：{manifest_issues[0].message}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = target_path.with_suffix(target_path.suffix + ".tmp")
        try:
            with zipfile.ZipFile(temporary, "w") as archive:
                archive.writestr(_zip_info("manifest.json"), manifest_bytes)
                for record, content in sorted(prepared, key=lambda item: item[0].path):
                    archive.writestr(_zip_info(record.path), content)
            os.replace(temporary, target_path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return manifest


class WorldPackageImporter:
    def __init__(self, world_packages_root: str | Path):
        self.root = Path(world_packages_root)
        self.installed_root = self.root / "installed"
        self.ledger = InstallLedger(self.root)

    def inspect(self, archive_path: str | Path) -> WorldPackageManifest:
        path = Path(archive_path)
        try:
            with zipfile.ZipFile(path, "r") as archive:
                files = [item for item in archive.infolist() if not item.is_dir()]
                if len(files) > MAX_FILE_COUNT + 1:
                    raise PackageFormatError("世界包文件数量超过首版限制")
                total = 0
                names: set[str] = set()
                for item in files:
                    normalized = validate_package_path(item.filename)
                    if normalized in names:
                        raise PackageFormatError("世界包包含重复路径")
                    names.add(normalized)
                    if item.file_size > MAX_FILE_SIZE:
                        raise PackageFormatError(f"文件超过大小限制：{item.filename}")
                    if item.file_size and (item.compress_size == 0 or item.file_size / item.compress_size > 200):
                        raise PackageFormatError(f"文件压缩比异常：{item.filename}")
                    total += item.file_size
                if total > MAX_PACKAGE_SIZE:
                    raise PackageFormatError("世界包总大小超过首版限制")
                if "manifest.json" not in names:
                    raise PackageFormatError("世界包缺少 manifest.json")
                try:
                    raw_manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as exc:
                    raise PackageFormatError("manifest.json 无法读取") from exc
                manifest = WorldPackageManifest.from_dict(raw_manifest)
                expected = {"manifest.json", *(item.path for item in manifest.assets)}
                if names != expected:
                    raise PackageFormatError("归档内容与 manifest 资产清单不一致")
                for record in manifest.assets:
                    content = archive.read(record.path)
                    if len(content) != record.size or _sha256(content) != record.sha256:
                        raise PackageFormatError(f"资产校验失败：{record.name}")
                    issues = scan_asset(record.path, content)
                    if issues:
                        raise PackageFormatError(f"导入安全扫描未通过：{issues[0].message}")
                return manifest
        except zipfile.BadZipFile as exc:
            raise PackageFormatError("文件不是有效的 AliveWorld 世界包") from exc

    def install(self, archive_path: str | Path) -> InstallRecord:
        archive_path = Path(archive_path)
        manifest = self.inspect(archive_path)
        package_hash = _sha256_file(archive_path)
        existing = self.ledger.find(manifest.package_id, manifest.version)
        if existing:
            install_dir = self.root / PurePosixPath(existing.manifest_path).parent
            if install_dir.is_dir() and existing.package_sha256 == package_hash:
                return existing
            if install_dir.is_dir():
                raise PackageFormatError("相同包 ID 与版本的文件内容不同，拒绝静默替换")
            raise PackageFormatError("安装账本存在记录，但世界包文件已丢失")

        final_dir = self.installed_root / manifest.package_id / manifest.version
        if final_dir.exists():
            raise PackageFormatError("目标安装目录已存在但未登记，请先检查本地文件")
        self.installed_root.mkdir(parents=True, exist_ok=True)
        temp_parent = final_dir.parent
        temp_parent.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(tempfile.mkdtemp(prefix=f".{manifest.version}-", dir=temp_parent))
        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                for item in archive.infolist():
                    if item.is_dir():
                        continue
                    relative = validate_package_path(item.filename)
                    destination = temp_dir.joinpath(*PurePosixPath(relative).parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item, "r") as source_file, destination.open("wb") as output:
                        shutil.copyfileobj(source_file, output)
            os.replace(temp_dir, final_dir)
            relative_manifest = (final_dir / "manifest.json").relative_to(self.root).as_posix()
            asset_records = tuple({
                "asset_id": item.asset_id,
                "type": item.asset_type,
                "path": (final_dir / PurePosixPath(item.path)).relative_to(self.root).as_posix(),
                "original_hash": item.sha256,
                "modified": False,
            } for item in manifest.assets)
            record = InstallRecord(
                package_id=manifest.package_id,
                version=manifest.version,
                name=manifest.name,
                installed_at=datetime.now(timezone.utc).isoformat(),
                manifest_path=relative_manifest,
                package_sha256=package_hash,
                assets=asset_records,
            )
            try:
                self.ledger.upsert(record)
            except Exception:
                shutil.rmtree(final_dir, ignore_errors=True)
                raise
            return record
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
