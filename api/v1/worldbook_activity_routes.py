from fastapi import APIRouter, HTTPException, Query
from core.session_manager import active_sessions
from core.worldbook_collaboration import load_books
from core.worldbook_activity import activity_page

router = APIRouter()


@router.get('/{session_id}/worldbook-activity')
def get_activity(session_id: str, offset: int = Query(0, ge=0),
                 limit: int = Query(30, ge=1, le=50), details: bool = False):
    game = active_sessions.get(session_id)
    if not game or not game.save_dir_path:
        raise HTTPException(404, '故事会话已失效')
    turns = list(game.history.get('story_turns', []))
    return activity_page(load_books(game.save_dir_path, turns), turns,
                         offset=offset, limit=limit, details=details)
