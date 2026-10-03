"""Single-process character asset CAS shared by editors and workshop publication."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import yaml
from core.character_profiles import CharacterProfileError, coordinate_character_write
from utils.atomic_yaml import save_yaml_atomic


class CharacterWriteError(ValueError):
    pass


def character_revision(asset):
    return hashlib.sha256(json.dumps(asset, ensure_ascii=False, sort_keys=True,
                                   separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


@contextmanager
def character_write_guard(path):
    # Lazy import avoids coupling pure card semantics to the story runtime.
    from core.session_manager import mutation_guard, MutationBusyError
    try:
        with mutation_guard('character-asset', str(Path(path).resolve()).casefold()):
            yield
    except MutationBusyError:
        raise CharacterWriteError('ASSET_BUSY：此角色卡正在保存，请稍后重试') from None


def read_character(path):
    path = Path(path)
    if path.is_symlink():
        raise CharacterWriteError('不允许通过链接写入角色卡')
    if not path.exists():
        return {}
    value = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise CharacterWriteError('角色卡文件格式错误，原文件未修改')
    return value


def write_character(path, changes, *, expected_revision=None, overwrite=True):
    with character_write_guard(path):
        current = read_character(path)
        if current and not overwrite:
            raise CharacterWriteError('已存在同名资产（角色卡），请明确确认覆盖')
        if expected_revision is not None and expected_revision != character_revision(current):
            raise CharacterWriteError('ASSET_REVISION_CONFLICT：角色卡已更新，请重新打开编辑器；当前草稿未保存')
        if current and 'role_fields' in changes and changes['role_fields'] != current.get('role_fields') and expected_revision is None:
            raise CharacterWriteError('ASSET_REVISION_REQUIRED：修改独立字段需要当前修订标识，请重新打开编辑器')
        try:
            output = coordinate_character_write(current, changes)
        except CharacterProfileError as exc:
            raise CharacterWriteError(str(exc)) from None
        save_yaml_atomic(path, output)
        return output
