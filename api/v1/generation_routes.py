"""Explicit cancellation for story/workshop requests; disconnect is not cancel."""
from functools import wraps
from typing import Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
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
                    return function(identity, payload, *args, **kwargs)
            except GenerationCancelled as exc:
                raise HTTPException(status_code=409, detail=f'generation_cancelled: {exc}') from exc
            except GenerationBusy as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        return wrapped
    return decorate


@router.post('/{kind}/{identity}/{request_id}/stop')
def stop_generation(kind: Literal['story', 'workshop'], identity: str, request_id: UUID):
    return cancel_generation((kind, identity), str(request_id))


@router.get('/{kind}/{identity}/{request_id}')
def get_generation_status(kind: Literal['story', 'workshop', 'character'], identity: str, request_id: UUID):
    scope = (kind, identity, str(request_id)) if kind == 'character' else (kind, identity)
    return generation_status(scope, str(request_id))
