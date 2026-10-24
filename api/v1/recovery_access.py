"""Resolve recovery ownership from existing sessions, never client file paths."""
import json
from pathlib import Path
import re
from fastapi import HTTPException


def recovery_directories(kind, identity):
    if kind == 'story':
        from core.session_manager import active_sessions
        game = active_sessions.get(identity)
        if game is None:
            raise HTTPException(404, '请先载入故事')
        directory = Path(game.save_dir_path) / 'generation_recovery'
        return directory, [directory]
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', identity):
        raise HTTPException(404, '工坊不存在')
    from core import worldbook_workshop_registry as worlds, asset_workshop_registry as assets, preference_workshop_registry as preferences
    for registry in (worlds, assets, preferences):
        owner_file = registry.WORKSHOP_DIR / f'{identity}.json'
        if not owner_file.is_file():
            continue
        owner = json.loads(owner_file.read_text(encoding='utf-8'))
        current = registry.WORKSHOP_DIR / 'generation_recovery' / identity
        directories = [current]
        target = owner.get('target_path')
        for path in registry.WORKSHOP_DIR.glob('*.json'):
            if path.stem == identity:
                continue
            record = json.loads(path.read_text(encoding='utf-8'))
            matches = (record.get('include_sensitive', False) == owner.get('include_sensitive', False)) if registry is preferences else (
                target and record.get('target_path') and Path(record['target_path']).resolve() == Path(target).resolve())
            if matches:
                directories.append(registry.WORKSHOP_DIR / 'generation_recovery' / path.stem)
        return current, directories
    raise HTTPException(404, '工坊不存在')
