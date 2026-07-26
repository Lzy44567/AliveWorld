"""Non-blocking, read-only application update routes."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

from core.update_checker import UpdateCheckError, check_for_updates


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
