"""Explicit cancellation for story/workshop requests; disconnect is not cancel."""
from functools import wraps
from typing import Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from core.generation_recovery import capture_generation, save_draft, read_drafts, delete_draft, failure_reason
from api.v1.recovery_access import recovery_directories
from core.generation_control import (
    GenerationBusy, GenerationCancelled, generation_scope, cancel_generation, generation_status,
)

router = APIRouter()


class GenerationPayload(BaseModel):
    generation_id: UUID = Field(default_factory=uuid4)


def controlled_generation(kind):
    def decorate(function):
        @wraps(function)
        def wrapped(identity, payload, *args, **kwargs):
            try:
                with generation_scope((kind, identity), str(payload.generation_id)):
                    with capture_generation() as captured:
                        try:
                            return function(identity, payload, *args, **kwargs)
                        except GenerationCancelled:
                            raise
                        except Exception as exc:
                            if captured['blocked']:
                                raise HTTPException(500, 'content_filter: 服务商过滤了本次输出，本次内容不保留，不自动重试。') from exc
                            if captured['text'] and not captured['blocked']:
                                try:
                                    directory, _ = recovery_directories(kind, identity)
                                    save_draft(directory, payload.generation_id, captured,
                                               getattr(payload, 'action', getattr(payload, 'message', '')),
                                               function.__name__, exc)
                                except (OSError, ValueError) as storage_error:
                                    raise HTTPException(500, '生成失败，残稿保存也失败；请立即复制当前可见文字并检查磁盘空间。') from storage_error
                            if failure_reason(captured['reason'], exc) == 'format':
                                raise HTTPException(500, '模型回复格式不完整，本次未保存为正式结果；已收到的可读文字请在“未完成内容”中查看。') from exc
                            raise
            except GenerationCancelled as exc:
                raise HTTPException(status_code=409, detail=f'generation_cancelled: {exc}') from exc
            except GenerationBusy as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        return wrapped
    return decorate


@router.post('/{kind}/{identity}/{request_id}/stop')
def stop_generation(kind: Literal['story', 'workshop'], identity: str, request_id: UUID):
    return cancel_generation((kind, identity), str(request_id))


@router.get('/{kind}/{identity}/recovery')
def list_recovery(kind: Literal['story', 'workshop'], identity: str):
    _, directories = recovery_directories(kind, identity)
    return {'drafts': read_drafts(directories)}


@router.delete('/{kind}/{identity}/recovery/{request_id}')
def remove_recovery(kind: Literal['story', 'workshop'], identity: str, request_id: UUID):
    _, directories = recovery_directories(kind, identity)
    delete_draft(directories, request_id)
    return {'status': 'deleted'}


@router.get('/{kind}/{identity}/{request_id}')
def get_generation_status(kind: Literal['story', 'workshop', 'character'], identity: str, request_id: UUID):
    scope = (kind, identity, str(request_id)) if kind == 'character' else (kind, identity)
    return generation_status(scope, str(request_id))
