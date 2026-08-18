"""HTTP boundary for local world-package files and one-click story creation."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api.v1.game_routes import start_prepared_game
from core.asset_lifecycle import AssetLifecycleError, normalize_asset_name
from core.session_manager import active_sessions
from core.world_packages.archive import MAX_PACKAGE_SIZE
from core.world_packages.authoring import AssetSelection, WorldPackageAuthoringService
from core.world_packages.models import PackageFormatError
from core.world_packages.service import WorldPackageService
from utils.file_io import init_save_folder
from utils.runtime_paths import PATHS


router = APIRouter()
SERVICE = WorldPackageService(PATHS.data_dir / "world_packages", PATHS.data_dir)
AUTHORING = WorldPackageAuthoringService(PATHS.data_dir)


class PackageStartPayload(BaseModel):
    save_name: str
    story_settings: dict[str, Any] = Field(default_factory=dict)


class UninstallPayload(BaseModel):
    mode: str = "safe"
    confirmed: bool = False
    delete_story_paths: list[str] = Field(default_factory=list)


class PackageAssetSelectionPayload(BaseModel):
    type: str
    name: str


class PackageExportPayload(BaseModel):
    package_id: str = ""
    version: str = "1.0.0"
    name: str
    author: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    adult: bool = False
    license: str = "unspecified"
    assets: list[PackageAssetSelectionPayload] = Field(default_factory=list)
    world_premise: str = ""
    opening: str = ""
    experience_preset: dict[str, Any] = Field(default_factory=dict)


async def _receive_archive(request: Request) -> Path:
    incoming = PATHS.data_dir / "world_packages" / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(prefix="upload-", suffix=".aliveworld", dir=incoming, delete=False)
    path = Path(handle.name)
    size = 0
    try:
        with handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_PACKAGE_SIZE:
                    raise PackageFormatError("世界包超过首版大小限制")
                handle.write(chunk)
        if size == 0:
            raise PackageFormatError("没有收到世界包文件")
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


@router.get("")
def list_packages():
    try:
        installed = SERVICE.list_packages()
        installed_keys = {(item["package_id"], item["version"]) for item in installed}
        official = [
            {**item, "installed": (item.get("package_id"), item.get("version")) in installed_keys}
            for item in AUTHORING.official_catalog()
        ]
        return {"packages": installed, "official_packages": official}
    except PackageFormatError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/authoring/assets")
def list_authoring_assets():
    """Return safe, name-based choices; never expose personal filesystem paths."""
    return {"assets": AUTHORING.catalog()}


@router.post("/official/{official_id}/start")
def start_official_package(official_id: str, payload: PackageStartPayload):
    """Build the bundled, inspectable package and enter it through the normal package path."""
    save_dir: Path | None = None
    record = None
    created_install = False
    try:
        archive, manifest = AUTHORING.export_official(official_id)
        save_name = normalize_asset_name(payload.save_name)
        save_dir = Path(init_save_folder(save_name))
        created_install = SERVICE.importer.ledger.find(manifest["package_id"], manifest["version"]) is None
        record = SERVICE.importer.install(archive)
        starter = SERVICE.materialize_story(record.package_id, record.version, save_dir)
        return start_prepared_game(
            save_name=save_name,
            save_dir_path=str(save_dir),
            world_premise=starter.world_premise,
            story_settings=starter.story_settings,
            opening=starter.opening,
            initial_state=starter.initial_state,
        )
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=f"已存在同名存档“{payload.save_name.strip()}”，请更换名称") from exc
    except (AssetLifecycleError, PackageFormatError) as exc:
        if created_install and record:
            SERVICE.rollback_install(record)
        if save_dir:
            shutil.rmtree(save_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        if created_install and record:
            SERVICE.rollback_install(record)
        if save_dir:
            shutil.rmtree(save_dir, ignore_errors=True)
        raise


@router.post("/authoring/export")
def export_authored_package(payload: PackageExportPayload):
    try:
        target, manifest = AUTHORING.export(
            metadata={
                "package_id": payload.package_id,
                "version": payload.version,
                "name": payload.name,
                "author": payload.author,
                "description": payload.description,
                "tags": payload.tags,
                "adult": payload.adult,
                "license": payload.license,
                "experience_preset": payload.experience_preset,
            },
            selections=[AssetSelection(item.type, item.name) for item in payload.assets],
            starter={
                "world_premise": payload.world_premise or payload.description,
                "opening": payload.opening,
                "story_settings": {},
            },
        )
        return {
            "status": "exported",
            "filename": target.name,
            "download_url": f"/api/v1/world-packages/authoring/exports/{target.name}",
            "manifest": manifest,
        }
    except PackageFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"世界包导出失败：{exc}") from exc


@router.get("/authoring/exports/{filename}")
def download_authored_package(filename: str):
    try:
        path = AUTHORING.download_path(filename)
        return FileResponse(path, media_type="application/zip", filename=path.name)
    except PackageFormatError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/inspect")
async def inspect_package(request: Request):
    path = await _receive_archive(request)
    try:
        return SERVICE.preview_archive(path)
    except PackageFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        path.unlink(missing_ok=True)


@router.post("/import")
async def import_package(request: Request):
    path = await _receive_archive(request)
    try:
        preview = SERVICE.preview_archive(path)
        if preview["status"] == "version_collision":
            raise PackageFormatError("相同包 ID 与版本的内容不同，不能覆盖")
        record = SERVICE.importer.install(path)
        return {"status": "installed", "record": record.to_dict(), "preview": preview}
    except PackageFormatError as exc:
        raise HTTPException(status_code=409 if "覆盖" in str(exc) else 400, detail=str(exc)) from exc
    finally:
        path.unlink(missing_ok=True)


@router.post("/import-and-start")
async def import_and_start_package(request: Request, save_name: str):
    """Primary player path: validate, install, create a story, and enter it."""
    path = await _receive_archive(request)
    save_dir: Path | None = None
    record = None
    created_install = False
    try:
        preview = SERVICE.preview_archive(path)
        if preview["status"] == "version_collision":
            raise PackageFormatError("相同包 ID 与版本的内容不同，不能覆盖")
        normalized_name = normalize_asset_name(save_name)
        save_dir = Path(init_save_folder(normalized_name))
        manifest = preview["manifest"]
        created_install = SERVICE.importer.ledger.find(manifest["package_id"], manifest["version"]) is None
        record = SERVICE.importer.install(path)
        starter = SERVICE.materialize_story(record.package_id, record.version, save_dir)
        return start_prepared_game(
            save_name=normalized_name,
            save_dir_path=str(save_dir),
            world_premise=starter.world_premise,
            story_settings=starter.story_settings,
            opening=starter.opening,
            initial_state=starter.initial_state,
        )
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=f"已存在同名存档“{save_name.strip()}”，请更换名称") from exc
    except AssetLifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PackageFormatError as exc:
        if created_install and record:
            SERVICE.rollback_install(record)
        if save_dir:
            shutil.rmtree(save_dir, ignore_errors=True)
        raise HTTPException(status_code=409 if "覆盖" in str(exc) else 400, detail=str(exc)) from exc
    except Exception:
        if created_install and record:
            SERVICE.rollback_install(record)
        if save_dir:
            shutil.rmtree(save_dir, ignore_errors=True)
        raise
    finally:
        path.unlink(missing_ok=True)


@router.get("/{package_id}/{version}")
def package_detail(package_id: str, version: str):
    try:
        return SERVICE.package_detail(package_id, version)
    except PackageFormatError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{package_id}/{version}/start")
def start_package_story(package_id: str, version: str, payload: PackageStartPayload):
    try:
        save_name = normalize_asset_name(payload.save_name)
        save_dir = Path(init_save_folder(save_name))
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=f"已存在同名存档“{payload.save_name.strip()}”，请更换名称") from exc
    except AssetLifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        starter = SERVICE.materialize_story(package_id, version, save_dir)
        settings = {**starter.story_settings, **payload.story_settings}
        return start_prepared_game(
            save_name=save_name,
            save_dir_path=str(save_dir),
            world_premise=starter.world_premise,
            story_settings=settings,
            opening=starter.opening,
            initial_state=starter.initial_state,
        )
    except PackageFormatError as exc:
        shutil.rmtree(save_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        shutil.rmtree(save_dir, ignore_errors=True)
        raise


@router.post("/{package_id}/{version}/uninstall")
def uninstall_package(package_id: str, version: str, payload: UninstallPayload):
    try:
        active_paths = {str(Path(game.save_dir_path).resolve()) for game in active_sessions.values() if game.save_dir_path}
        selected = tuple(str(Path(path).resolve()) for path in payload.delete_story_paths)
        if active_paths.intersection(selected):
            raise PackageFormatError("选中的故事正在游玩，请先切换或关闭该故事后再删除")
        return SERVICE.uninstall(
            package_id,
            version,
            mode=payload.mode,
            confirmed=payload.confirmed,
            delete_story_paths=selected,
        )
    except PackageFormatError as exc:
        raise HTTPException(status_code=409 if "确认" in str(exc) else 400, detail=str(exc)) from exc
