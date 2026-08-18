"""Creator-facing orchestration for exporting selected personal assets.

This module deliberately owns selection resolution and starter generation so the
HTTP layer never accepts arbitrary filesystem paths and the archive layer stays
focused on the portable format itself.
"""

from __future__ import annotations

import json
import hashlib
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from core.world_packages.archive import AssetSource, WorldPackageExporter
from core.world_packages.identity import ensure_yaml_asset_id
from core.world_packages.models import PackageFormatError, new_package_id, validate_version


AUTHORING_ASSET_TYPES = ("worldbooks", "characters", "styles", "entities")


@dataclass(frozen=True)
class AssetSelection:
    asset_type: str
    name: str


def _asset_summary(asset_type: str, path: Path) -> dict[str, Any] | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict) or not str(data.get("name", "")).strip():
        return None
    tags = data.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    description = data.get("description", data.get("overview", data.get("motive", data.get("content", ""))))
    return {
        "type": asset_type,
        "name": str(data["name"]).strip(),
        "tags": [str(item) for item in tags if str(item).strip()],
        "description": str(description or "")[:240],
        "is_template": path.name.endswith(".template.yml") or data.get("is_template") is True or "模板" in tags,
    }


def _safe_export_stem(name: str) -> str:
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name or "").strip()).strip(" .")
    if not stem:
        raise PackageFormatError("世界包名称不能为空")
    return stem[:100]


class WorldPackageAuthoringService:
    def __init__(self, data_root: str | Path):
        self.data_root = Path(data_root)
        self.export_root = self.data_root / "world_packages" / "exports"

    def catalog(self) -> list[dict[str, Any]]:
        assets: list[dict[str, Any]] = []
        for asset_type in AUTHORING_ASSET_TYPES:
            directory = self.data_root / asset_type
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.yml")):
                summary = _asset_summary(asset_type, path)
                if summary:
                    assets.append(summary)
        return assets

    def official_catalog(self) -> list[dict[str, Any]]:
        directory = self.data_root / "world_packages"
        if not directory.is_dir():
            return []
        results: list[dict[str, Any]] = []
        for path in sorted(directory.glob("*.template.json")):
            try:
                definition = json.loads(path.read_text(encoding="utf-8"))
                official_id = str(definition.get("official_id", "")).strip()
                metadata = definition.get("metadata", {})
                assets = definition.get("assets", [])
                if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,63}", official_id):
                    continue
                if not isinstance(metadata, dict) or not isinstance(assets, list):
                    continue
                results.append({
                    "official_id": official_id,
                    **metadata,
                    "asset_count": len(assets),
                })
            except (OSError, json.JSONDecodeError, AttributeError):
                continue
        return results

    def export_official(self, official_id: str) -> tuple[Path, dict[str, Any]]:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,63}", str(official_id or "")):
            raise PackageFormatError("官方演示世界标识无效")
        path = self.data_root / "world_packages" / f"{official_id}.template.json"
        if not path.is_file():
            raise PackageFormatError("官方演示世界不存在")
        try:
            definition = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PackageFormatError("官方演示世界配置损坏") from exc
        if definition.get("official_id") != official_id:
            raise PackageFormatError("官方演示世界身份不一致")
        metadata = definition.get("metadata")
        raw_assets = definition.get("assets")
        if not isinstance(metadata, dict) or not isinstance(raw_assets, list):
            raise PackageFormatError("官方演示世界配置不完整")
        selections = [
            AssetSelection(str(item.get("type", "")), str(item.get("name", "")))
            for item in raw_assets if isinstance(item, dict)
        ]
        if len(selections) != len(raw_assets):
            raise PackageFormatError("官方演示世界资产选择无效")
        return self.export(
            metadata=metadata,
            selections=selections,
            starter=definition.get("starter", {}),
            templates_only=True,
        )

    def _resolve_path(self, asset_type: str, name: str, *, templates_only: bool = False) -> Path | None:
        directory = self.data_root / asset_type
        if not directory.is_dir():
            return None
        matches: list[Path] = []
        for path in directory.glob("*.yml"):
            summary = _asset_summary(asset_type, path)
            if summary and summary["name"] == name and (not templates_only or summary["is_template"]):
                matches.append(path)
        matches.sort(key=lambda item: item.name.endswith(".template.yml"))
        return matches[0] if matches else None

    def resolve(self, selections: Iterable[AssetSelection], *, templates_only: bool = False) -> list[AssetSource]:
        resolved: list[AssetSource] = []
        seen: set[tuple[str, str]] = set()
        for selection in selections:
            asset_type = str(selection.asset_type or "").strip()
            name = str(selection.name or "").strip()
            key = (asset_type, name.casefold())
            if asset_type not in AUTHORING_ASSET_TYPES:
                raise PackageFormatError(f"不能打包未知资产类型：{asset_type}")
            if not name or key in seen:
                raise PackageFormatError("世界包资产选择无效或重复")
            seen.add(key)
            path = self._resolve_path(asset_type, name, templates_only=templates_only)
            if not path:
                raise PackageFormatError(f"找不到待打包资产：{name}")
            resolved.append(AssetSource(
                asset_type=asset_type,
                path=path,
                name=name,
                asset_id=ensure_yaml_asset_id(path),
            ))
        return resolved

    def export(
        self,
        *,
        metadata: dict[str, Any],
        selections: Iterable[AssetSelection],
        starter: dict[str, Any] | None = None,
        templates_only: bool = False,
    ) -> tuple[Path, dict[str, Any]]:
        sources = self.resolve(selections, templates_only=templates_only)
        if not sources:
            raise PackageFormatError("请至少选择一项世界书、角色、文风或实体资产")
        starter_payload = {
            "world_premise": str((starter or {}).get("world_premise", "")).strip(),
            "opening": str((starter or {}).get("opening", "")).strip(),
            "story_settings": dict((starter or {}).get("story_settings", {})),
        }
        package_id = str(metadata.get("package_id", "")).strip() or new_package_id()
        version = validate_version(metadata.get("version", "1.0.0"))
        package = {
            "package_id": package_id,
            "version": version,
            "name": metadata.get("name", ""),
            "author": metadata.get("author", ""),
            "description": metadata.get("description", ""),
            "tags": tuple(metadata.get("tags", [])),
            "adult": bool(metadata.get("adult", False)),
            "license": metadata.get("license", "unspecified"),
            "min_app_version": metadata.get("min_app_version", "1.6.0-dev.5"),
            "experience_preset": metadata.get("experience_preset", {}),
        }

        entrypoints: dict[str, Any] = {}
        by_type: dict[str, list[str]] = {asset_type: [] for asset_type in AUTHORING_ASSET_TYPES}
        for source in sources:
            by_type[source.asset_type].append(source.asset_id)
        if by_type["worldbooks"]:
            entrypoints["main_worldbook"] = by_type["worldbooks"][0]
        if by_type["characters"]:
            entrypoints["characters"] = by_type["characters"]
        if by_type["styles"]:
            entrypoints["style"] = by_type["styles"][0]
        if by_type["entities"]:
            entrypoints["entities"] = by_type["entities"]

        self.export_root.mkdir(parents=True, exist_ok=True)
        target = self.export_root / f"{_safe_export_stem(str(package['name']))}-{package['version']}.aliveworld"
        with tempfile.TemporaryDirectory(prefix="aliveworld-starter-") as temp:
            starter_path = Path(temp) / "starter.json"
            starter_path.write_text(json.dumps(starter_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            starter_id = f"awasset_{hashlib.sha256(f'{package_id}:starter'.encode('utf-8')).hexdigest()[:32]}"
            sources.append(AssetSource("starter", starter_path, name="默认故事起点", asset_id=starter_id))
            entrypoints["starter"] = starter_id
            package["entrypoints"] = entrypoints
            manifest = WorldPackageExporter().export(target, package=package, assets=sources)
        return target, manifest.to_dict()

    def download_path(self, filename: str) -> Path:
        name = Path(str(filename or "")).name
        if name != filename or not name.endswith(".aliveworld"):
            raise PackageFormatError("世界包下载名称无效")
        path = self.export_root / name
        if not path.is_file():
            raise PackageFormatError("导出的世界包不存在")
        return path
