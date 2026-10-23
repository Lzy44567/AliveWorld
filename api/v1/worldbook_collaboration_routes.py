"""Story-local worldbook priority and conflict review endpoints."""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, StrictBool, Field, model_validator

from core.session_manager import active_sessions, mutation_guard, save_identity, MutationBusyError
from core.worldbook_collaboration import load_books, fingerprint, public_collaboration, decide_conflict, decide_conflicts
from utils.file_io import save_game_data

router = APIRouter()


class ConflictDecision(BaseModel):
    conflict_id: str = Field(min_length=1, max_length=200)
    decision: Literal['disable', 'restore']


class CollaborationChange(BaseModel):
    expected_revision: str
    primary_book: str | None = None
    auto_disable: StrictBool | None = None
    review: StrictBool | None = None
    conflict_id: str | None = None
    decision: Literal['disable', 'restore'] | None = None
    decisions: list[ConflictDecision] | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode='after')
    def exclusive_batch(self):
        if self.decisions is not None and any(value is not None for value in (
                self.conflict_id, self.decision, self.primary_book, self.auto_disable, self.review)):
            raise ValueError('批量审阅不能同时修改其他协作设置')
        return self


def session(session_id):
    game = active_sessions.get(session_id)
    if not game or not game.save_dir_path:
        raise HTTPException(404, '故事会话已失效')
    return game


@router.get('/{session_id}/worldbook-collaboration')
def get_collaboration(session_id: str):
    game = session(session_id)
    turns = game.history.get('story_turns', [])
    return public_collaboration(game.worldbook_collaboration, load_books(game.save_dir_path, turns), turns)


@router.patch('/{session_id}/worldbook-collaboration')
def update_collaboration(session_id: str, payload: CollaborationChange):
    game = session(session_id)
    try:
        with mutation_guard('story', save_identity(game.save_dir_path)):
            original = game.worldbook_collaboration
            if fingerprint(original) != payload.expected_revision:
                raise HTTPException(409, '世界书协作状态已更新，请刷新后重试')
            turns = game.history.get('story_turns', [])
            books = load_books(game.save_dir_path, turns)
            updated = dict(original)
            if payload.primary_book is not None:
                if payload.primary_book and (payload.primary_book not in books or not books[payload.primary_book].get('is_active', True)):
                    raise HTTPException(400, '只能选择本局已启用的世界书')
                updated['primary_book'] = payload.primary_book
            for field in ('auto_disable', 'review'):
                value = getattr(payload, field)
                if value is not None:
                    updated[field] = value
            if payload.conflict_id is not None or payload.decision is not None:
                updated = decide_conflict(updated, payload.conflict_id, payload.decision, books=books, turns=turns)
            if payload.decisions is not None:
                updated = decide_conflicts(updated, [item.model_dump() for item in payload.decisions], books=books, turns=turns)
            game.worldbook_collaboration = updated
            try:
                save_game_data(game.save_dir_path, game.export_save_data())
            except OSError:
                game.worldbook_collaboration = original
                raise HTTPException(500, '保存失败，协作设置保持不变') from None
            return public_collaboration(updated, books, turns)
    except MutationBusyError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
