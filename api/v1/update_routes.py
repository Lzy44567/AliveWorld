"""Non-blocking, read-only application update routes."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

from core.update_checker import UpdateCheckError, check_for_updates
from core.update_installer import UPDATE_MANAGER, UpdateInstallError


router = APIRouter()


@router.get("/check")
async def check_update(include_prerelease: bool = Query(default=True)):
    try:
        return await asyncio.to_thread(
            check_for_updates,
            include_prerelease=include_prerelease,
        )
    except UpdateCheckError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/prepare")
async def prepare_update(include_prerelease: bool = Query(default=True)):
    try:
        release = await asyncio.to_thread(
            check_for_updates,
            include_prerelease=include_prerelease,
        )
        if not release.get("update_available"):
            raise UpdateInstallError("当前没有可安装的新版本。")
        return UPDATE_MANAGER.start_prepare(release)
    except UpdateCheckError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpdateInstallError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/status")
async def update_status():
    return UPDATE_MANAGER.snapshot()


@router.post("/cancel")
async def cancel_update():
    try:
        return UPDATE_MANAGER.cancel()
    except UpdateInstallError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/install")
async def install_update():
    try:
        return UPDATE_MANAGER.begin_install()
    except UpdateInstallError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
