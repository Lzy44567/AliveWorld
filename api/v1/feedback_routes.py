"""Narrow, local-only feedback preview and diagnostic export API."""

from __future__ import annotations

import io
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.feedback import FeedbackDraft, build_diagnostic_zip, build_feedback_preview, feedback_context


router = APIRouter()


class FeedbackPayload(BaseModel):
    category: str = "bug"
    title: str = Field(default="", max_length=160)
    actual: str = Field(default="", max_length=8000)
    expected: str = Field(default="", max_length=8000)
    steps: str = Field(default="", max_length=8000)
    trace_id: str = Field(default="", max_length=80)
    selected_log_ids: list[str] = Field(default_factory=list, max_length=50)

    def to_domain(self) -> FeedbackDraft:
        return FeedbackDraft(**self.model_dump())


@router.get("/context")
async def get_feedback_context():
    return feedback_context()


@router.post("/preview")
async def preview_feedback(payload: FeedbackPayload):
    return build_feedback_preview(payload.to_domain())


@router.post("/export")
async def export_feedback(payload: FeedbackPayload):
    try:
        content, filename = build_diagnostic_zip(payload.to_domain())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return StreamingResponse(io.BytesIO(content), media_type="application/zip", headers=headers)
