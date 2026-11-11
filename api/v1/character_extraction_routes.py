"""Explicit local-card extraction; never overwrites the source or global cards."""
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.session_manager import active_sessions, mutation_guard, save_identity, MutationBusyError
from core.asset_lifecycle import find_yaml_asset, filename_for_asset
from core.character_asset_write import read_character, character_revision, write_character, CharacterWriteError
from core.character_extraction import prepare_character_card
from core.character_experiences import with_experiences
from utils.runtime_paths import PATHS

router = APIRouter()


class ExtractionPayload(BaseModel):
    name: str
    expected_revision: str
    profile: dict
    reviewed: bool = False
    include_experiences: bool = False
    experiences: str = ''


def source(session_id, name):
    game = active_sessions.get(session_id)
    if not game or not game.save_dir_path:
        raise HTTPException(404, '请先载入故事')
    path = find_yaml_asset(Path(game.save_dir_path) / 'characters', name)
    if path is None:
        raise HTTPException(404, '局内角色不存在')
    return game, path


@router.get('/{session_id}/character-extraction/{name}')
def preview(session_id: str, name: str):
    try:
        game, path = source(session_id, name)
        with mutation_guard('story', save_identity(game.save_dir_path)):
            card = read_character(path)
            return {'profile': prepare_character_card(card, card['name']),
                    'revision': character_revision(card)}
    except MutationBusyError as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@router.post('/{session_id}/character-extraction/{name}')
def save(session_id: str, name: str, payload: ExtractionPayload):
    if not payload.reviewed:
        raise HTTPException(400, '请先审阅人设并确认保存')
    try:
        game, path = source(session_id, name)
        with mutation_guard('story', save_identity(game.save_dir_path)):
            if character_revision(read_character(path)) != payload.expected_revision:
                raise HTTPException(409, '来源角色已修改，请重新打开提取预览')
            card = prepare_character_card(payload.profile, payload.name)
            if payload.include_experiences:
                card = with_experiences(card, payload.experiences, Path(game.save_dir_path).name)
            directory = PATHS.data_dir / 'characters'
            if find_yaml_asset(directory, card['name']):
                raise HTTPException(409, '已有同名角色，请修改新卡名称；不会覆盖原卡')
            write_character(directory / filename_for_asset(card['name']), card, overwrite=False)
            return {'name': card['name']}
    except (MutationBusyError, CharacterWriteError) as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except OSError:
        raise HTTPException(500, '保存失败，原故事及已有角色卡未修改') from None
