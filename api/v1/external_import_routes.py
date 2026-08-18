"""HTTP boundary for safe external character-card and lorebook imports."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from core.external_formats import ExternalAssetImportService, ExternalFormatError
from utils.runtime_paths import PATHS


router = APIRouter()
SERVICE = ExternalAssetImportService(PATHS.data_dir)
MAX_UPLOAD_BYTES = 16 * 1024 * 1024


async def _read_upload(request: Request) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="外部资产文件超过 16 MB 上传限制")
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(status_code=400, detail="没有收到外部资产文件")
    return b"".join(chunks)


@router.post("/inspect")
async def inspect_external_asset(
    request: Request,
    filename: str = Query("external.json", max_length=255),
    kind: str = Query("auto", pattern="^(auto|character|lorebook)$"),
):
    try:
        preview = SERVICE.inspect(await _read_upload(request), filename, kind)
        return preview.to_dict(include_asset=False)
    except ExternalFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import")
async def import_external_asset(
    request: Request,
    filename: str = Query("external.json", max_length=255),
    kind: str = Query("auto", pattern="^(auto|character|lorebook)$"),
    name: str = Query("", max_length=120),
):
    try:
        return SERVICE.commit(await _read_upload(request), filename, kind, name)
    except ExternalFormatError as exc:
        status = 409 if "同名资产" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
