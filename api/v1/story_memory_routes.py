"""Story-memory inspection and explicit debug compaction endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.session_manager import active_sessions


router = APIRouter()


class CompactMemoryPayload(BaseModel):
    force: bool = False


def _game(session_id: str):
    game = active_sessions.get(session_id)
    if not game:
        raise HTTPException(status_code=404, detail="会话失效")
    return game


@router.get("/{session_id}/story-memory")
def get_story_memory(session_id: str):
    game = _game(session_id)
    return {
        **game.story_memory.status(game.history.get("story_turns", [])),
        "events": game.story_memory.export_state().get("story_events", []),
    }


@router.post("/{session_id}/story-memory/compact")
def compact_story_memory(session_id: str, payload: CompactMemoryPayload):
    game = _game(session_id)
    result = game.story_memory.compact_now(game.history.get("story_turns", []), force=payload.force)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return {**result, "status": game.story_memory.status(game.history.get("story_turns", []))}
