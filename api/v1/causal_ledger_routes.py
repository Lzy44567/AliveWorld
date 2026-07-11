from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.session_manager import active_sessions
from utils.file_io import save_game_data


router = APIRouter()


class InfluencePayload(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)


def _game(session_id):
    game = active_sessions.get(session_id)
    if not game:
        raise HTTPException(status_code=404, detail="会话失效")
    return game


def _persist(game):
    game.undercurrent.sync_influence_refs()
    game._sync_entities_to_local()
    save_game_data(game.save_dir_path, game.export_save_data())


@router.get("/{session_id}/causal-ledger")
def get_causal_ledger(session_id: str):
    game = _game(session_id)
    return {
        "turn_count": game.undercurrent.causal_ledger.turn_count,
        "influences": game.undercurrent.causal_ledger.export(),
    }


@router.post("/{session_id}/causal-ledger")
def create_influence(session_id: str, payload: InfluencePayload):
    game = _game(session_id)
    data = dict(payload.data)
    if not data.get("created_world_time"):
        data["created_world_time"] = str(game.state.get("properties", {}).get("当前时间", ""))
    influence = game.undercurrent.causal_ledger.add(data, current_tick=game.undercurrent.causal_ledger.turn_count)
    if not influence:
        raise HTTPException(status_code=400, detail="影响内容无效或 ID 重复")
    _persist(game)
    return influence.to_dict()


@router.post("/{session_id}/causal-ledger/{influence_id}")
def update_influence(session_id: str, influence_id: str, payload: InfluencePayload):
    game = _game(session_id)
    influence = game.undercurrent.causal_ledger.update({**payload.data, "id": influence_id})
    if not influence:
        raise HTTPException(status_code=404, detail="影响不存在")
    _persist(game)
    return influence.to_dict()


@router.delete("/{session_id}/causal-ledger/{influence_id}")
def delete_influence(session_id: str, influence_id: str):
    game = _game(session_id)
    influence = game.undercurrent.causal_ledger.remove(influence_id)
    if not influence:
        raise HTTPException(status_code=404, detail="影响不存在")
    _persist(game)
    return {"status": "success"}
