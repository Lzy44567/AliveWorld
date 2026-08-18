"""Versioned manifest and installation records for AliveWorld packages."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from core.story_settings import DEFAULT_STORY_SETTINGS


SCHEMA_VERSION = 1
PACKAGE_EXTENSION = ".aliveworld"
ASSET_TYPES = frozenset({"worldbooks", "characters", "styles", "entities", "images", "workflows", "starter"})
ID_PATTERN = re.compile(r"^(?:awpkg|awasset)_[0-9a-f]{32}$")
VERSION_PATTERN = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]{0,63}$")


class PackageFormatError(ValueError):
    """The package is malformed, unsafe, or incompatible with this schema."""


def new_package_id() -> str:
    return f"awpkg_{uuid.uuid4().hex}"


def new_asset_id() -> str:
    return f"awasset_{uuid.uuid4().hex}"


def validate_identifier(value: Any, *, prefix: str) -> str:
    identifier = str(value or "").strip().lower()
    if not ID_PATTERN.fullmatch(identifier) or not identifier.startswith(f"{prefix}_"):
        raise PackageFormatError(f"无效的 {prefix} 标识")
    return identifier


def validate_version(value: Any) -> str:
    version = str(value or "").strip()
    if not VERSION_PATTERN.fullmatch(version):
        raise PackageFormatError("世界包版本格式无效")
    return version


def validate_package_path(value: Any, *, asset_type: str | None = None) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise PackageFormatError("世界包包含不安全的相对路径")
    normalized = path.as_posix()
    if normalized != raw or ":" in raw or raw.startswith("/"):
        raise PackageFormatError("世界包路径必须是规范的 POSIX 相对路径")
    if asset_type and (not path.parts or path.parts[0] != asset_type):
        raise PackageFormatError(f"资产路径必须位于 {asset_type}/ 下")
    return normalized


def _text(value: Any, *, name: str, maximum: int, required: bool = False) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise PackageFormatError(f"{name}不能为空")
    if len(result) > maximum:
        raise PackageFormatError(f"{name}过长")
    return result


@dataclass(frozen=True)
class AssetRecord:
    asset_id: str
    asset_type: str
    name: str
    path: str
    sha256: str
    size: int
    dependencies: tuple[str, ...] = ()
    optional: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "asset_id", validate_identifier(self.asset_id, prefix="awasset"))
        if self.asset_type not in ASSET_TYPES:
            raise PackageFormatError(f"不支持的资产类型：{self.asset_type}")
        object.__setattr__(self, "name", _text(self.name, name="资产名称", maximum=120, required=True))
        object.__setattr__(self, "path", validate_package_path(self.path, asset_type=self.asset_type))
        digest = str(self.sha256 or "").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise PackageFormatError("资产 SHA-256 无效")
        object.__setattr__(self, "sha256", digest)
        if not isinstance(self.size, int) or self.size < 0:
            raise PackageFormatError("资产大小无效")
        dependencies = tuple(validate_identifier(item, prefix="awasset") for item in self.dependencies)
        if self.asset_id in dependencies:
            raise PackageFormatError("资产不能依赖自身")
        object.__setattr__(self, "dependencies", dependencies)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "type": self.asset_type,
            "name": self.name,
            "path": self.path,
            "sha256": self.sha256,
            "size": self.size,
            "dependencies": list(self.dependencies),
            "optional": self.optional,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> "AssetRecord":
        if not isinstance(raw, dict):
            raise PackageFormatError("资产记录必须是对象")
        return cls(
            asset_id=raw.get("asset_id", ""),
            asset_type=str(raw.get("type", "")),
            name=raw.get("name", ""),
            path=raw.get("path", ""),
            sha256=raw.get("sha256", ""),
            size=raw.get("size", -1),
            dependencies=tuple(raw.get("dependencies", [])),
            optional=bool(raw.get("optional", False)),
        )


@dataclass(frozen=True)
class WorldPackageManifest:
    package_id: str
    version: str
    name: str
    author: str
    description: str = ""
    tags: tuple[str, ...] = ()
    adult: bool = False
    license: str = "unspecified"
    min_app_version: str = "1.6.0-dev.1"
    assets: tuple[AssetRecord, ...] = ()
    entrypoints: dict[str, Any] = field(default_factory=dict)
    recommended_settings: dict[str, Any] = field(default_factory=dict)
    experience_preset: dict[str, Any] = field(default_factory=dict)
    source: dict[str, str] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise PackageFormatError(f"不支持的世界包格式版本：{self.schema_version}")
        object.__setattr__(self, "package_id", validate_identifier(self.package_id, prefix="awpkg"))
        object.__setattr__(self, "version", validate_version(self.version))
        object.__setattr__(self, "name", _text(self.name, name="世界包名称", maximum=120, required=True))
        object.__setattr__(self, "author", _text(self.author, name="作者", maximum=120, required=True))
        object.__setattr__(self, "description", _text(self.description, name="简介", maximum=4000))
        object.__setattr__(self, "license", _text(self.license, name="许可证", maximum=120) or "unspecified")
        object.__setattr__(self, "min_app_version", _text(self.min_app_version, name="最低版本", maximum=64))
        tags = tuple(dict.fromkeys(_text(item, name="标签", maximum=40) for item in self.tags if str(item).strip()))
        object.__setattr__(self, "tags", tags)
        assets = tuple(self.assets)
        ids = [item.asset_id for item in assets]
        paths = [item.path for item in assets]
        if len(ids) != len(set(ids)) or len(paths) != len(set(paths)):
            raise PackageFormatError("世界包中存在重复的资产 ID 或路径")
        known = set(ids)
        graph = {item.asset_id: set(item.dependencies) for item in assets}
        for item in assets:
            missing = set(item.dependencies) - known
            if missing:
                raise PackageFormatError(f"资产 {item.name} 引用了包内不存在的依赖")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(asset_id: str) -> None:
            if asset_id in visiting:
                raise PackageFormatError("世界包资产依赖图存在循环")
            if asset_id in visited:
                return
            visiting.add(asset_id)
            for dependency in graph[asset_id]:
                visit(dependency)
            visiting.remove(asset_id)
            visited.add(asset_id)

        for asset_id in graph:
            visit(asset_id)
        object.__setattr__(self, "assets", assets)
        if not isinstance(self.entrypoints, dict) or not isinstance(self.recommended_settings, dict):
            raise PackageFormatError("入口与推荐设置必须是对象")
        unknown_recommended = set(self.recommended_settings) - set(DEFAULT_STORY_SETTINGS)
        if unknown_recommended:
            raise PackageFormatError(f"推荐设置包含不可写入的字段：{sorted(unknown_recommended)[0]}")
        if not isinstance(self.experience_preset, dict):
            raise PackageFormatError("体验预设必须是对象")
        allowed_preset_keys = {"defaults", "visibility", "required_capabilities", "locked_keys"}
        if set(self.experience_preset) - allowed_preset_keys:
            raise PackageFormatError("体验预设包含未知字段")
        clean_preset: dict[str, Any] = {}
        for key in ("defaults", "visibility"):
            value = self.experience_preset.get(key, {})
            if not isinstance(value, dict):
                raise PackageFormatError(f"体验预设 {key} 必须是对象")
            unknown_settings = set(value) - set(DEFAULT_STORY_SETTINGS)
            if unknown_settings:
                raise PackageFormatError(f"体验预设包含不可写入的设置：{sorted(unknown_settings)[0]}")
            clean_preset[key] = dict(value)
        for key in ("required_capabilities", "locked_keys"):
            value = self.experience_preset.get(key, [])
            if not isinstance(value, list):
                raise PackageFormatError(f"体验预设 {key} 必须是列表")
            clean_preset[key] = list(dict.fromkeys(_text(item, name="体验预设项目", maximum=80, required=True) for item in value))
        if set(clean_preset["locked_keys"]) - set(DEFAULT_STORY_SETTINGS):
            raise PackageFormatError("体验预设锁定了非局内设置")
        object.__setattr__(self, "experience_preset", clean_preset)
        if not isinstance(self.source, dict):
            raise PackageFormatError("更新来源必须是对象")
        entrypoint_ids: list[str] = []
        for value in self.entrypoints.values():
            if isinstance(value, str) and value:
                entrypoint_ids.append(value)
            elif isinstance(value, list):
                entrypoint_ids.extend(str(item) for item in value)
        if set(entrypoint_ids) - known:
            raise PackageFormatError("世界包入口引用了不存在的资产 ID")
        clean_source = {}
        for key, value in self.source.items():
            clean_key = _text(key, name="来源字段", maximum=40, required=True)
            clean_value = _text(value, name="来源值", maximum=500)
            if re.match(r"^[A-Za-z]:[\\/]", clean_value) or clean_value.startswith(("/", "\\\\")):
                raise PackageFormatError("更新来源不能包含本机绝对路径")
            clean_source[clean_key] = clean_value
        object.__setattr__(self, "source", clean_source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "package_id": self.package_id,
            "version": self.version,
            "name": self.name,
            "author": self.author,
            "description": self.description,
            "tags": list(self.tags),
            "adult": self.adult,
            "license": self.license,
            "min_app_version": self.min_app_version,
            "assets": [item.to_dict() for item in self.assets],
            "entrypoints": self.entrypoints,
            "recommended_settings": self.recommended_settings,
            "experience_preset": self.experience_preset,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> "WorldPackageManifest":
        if not isinstance(raw, dict):
            raise PackageFormatError("manifest.json 必须是对象")
        return cls(
            schema_version=raw.get("schema_version", 0),
            package_id=raw.get("package_id", ""),
            version=raw.get("version", ""),
            name=raw.get("name", ""),
            author=raw.get("author", ""),
            description=raw.get("description", ""),
            tags=tuple(raw.get("tags", [])),
            adult=bool(raw.get("adult", False)),
            license=raw.get("license", "unspecified"),
            min_app_version=raw.get("min_app_version", ""),
            assets=tuple(AssetRecord.from_dict(item) for item in raw.get("assets", [])),
            entrypoints=raw.get("entrypoints", {}),
            recommended_settings=raw.get("recommended_settings", {}),
            experience_preset=raw.get("experience_preset", {}),
            source=raw.get("source", {}),
        )


@dataclass(frozen=True)
class InstallRecord:
    package_id: str
    version: str
    name: str
    installed_at: str
    manifest_path: str
    package_sha256: str
    assets: tuple[dict[str, Any], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "package_id", validate_identifier(self.package_id, prefix="awpkg"))
        object.__setattr__(self, "version", validate_version(self.version))
        object.__setattr__(self, "manifest_path", validate_package_path(self.manifest_path))
        digest = str(self.package_sha256 or "").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise PackageFormatError("世界包安装哈希无效")
        object.__setattr__(self, "package_sha256", digest)
        object.__setattr__(self, "assets", tuple(_validate_installed_asset(item) for item in self.assets))

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "version": self.version,
            "name": self.name,
            "installed_at": self.installed_at,
            "manifest_path": self.manifest_path,
            "package_sha256": self.package_sha256,
            "assets": [dict(item) for item in self.assets],
        }

    @classmethod
    def from_dict(cls, raw: Any) -> "InstallRecord":
        if not isinstance(raw, dict):
            raise PackageFormatError("安装记录无效")
        return cls(
            package_id=raw.get("package_id", ""),
            version=raw.get("version", ""),
            name=_text(raw.get("name", ""), name="世界包名称", maximum=120, required=True),
            installed_at=str(raw.get("installed_at", "")),
            manifest_path=raw.get("manifest_path", ""),
            package_sha256=str(raw.get("package_sha256", "")),
            assets=tuple(raw.get("assets", [])),
        )


def _validate_installed_asset(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise PackageFormatError("安装资产记录无效")
    digest = str(raw.get("original_hash", "")).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise PackageFormatError("安装资产哈希无效")
    return {
        "asset_id": validate_identifier(raw.get("asset_id", ""), prefix="awasset"),
        "type": str(raw.get("type", "")),
        "path": validate_package_path(raw.get("path", "")),
        "original_hash": digest,
        "modified": bool(raw.get("modified", False)),
    }
