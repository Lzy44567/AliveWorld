"""Pure versioned role-card semantics and compatibility-write coordination."""
from copy import deepcopy

ROLE_LIMITS = {'description': 16000, 'personality': 8000, 'scenario': 8000,
               'dialogue_examples': 8000, 'first_message': 8000}
ROLE_SEMANTICS = 'role_fields_v1'


class CharacterProfileError(ValueError):
    pass


def compatibility_fields(fields):
    sections = [fields['description']] if fields['description'] else []
    for label, key in (('性格', 'personality'), ('场景设定', 'scenario'), ('对话示例', 'dialogue_examples')):
        if fields[key]:
            sections.append(f'【{label}】\n{fields[key]}')
    return '\n\n'.join(sections), fields['first_message']


def validate_role_fields(value):
    if not isinstance(value, dict) or set(value) != {'version', *ROLE_LIMITS}:
        raise CharacterProfileError('role_fields 必须包含版本及完整的五项文本字段')
    if type(value['version']) is not int or value['version'] != 1:
        raise CharacterProfileError('role_fields 版本暂不支持')
    for key, limit in ROLE_LIMITS.items():
        if not isinstance(value[key], str):
            raise CharacterProfileError(f'{key} 必须是文本')
        if len(value[key]) > limit:
            raise CharacterProfileError(f'{key} 长度 {len(value[key])} 超过上限 {limit}')
    total = sum(len(value[key]) for key in ROLE_LIMITS)
    if total > 32000:
        raise CharacterProfileError(f'角色独立字段总长 {total} 超过上限 32000')
    if len(compatibility_fields(value)[0]) > 32000:
        raise CharacterProfileError('合并描述超过上限 32000')
    return deepcopy(value)


def coordinate_character_write(current, changes):
    """Explicit structure wins; changed legacy text clears structure, never source."""
    current = current if isinstance(current, dict) else {}
    result = deepcopy({**current, **changes})
    if 'role_fields' in changes:
        if changes['role_fields'] is not None:
            result['role_fields'] = validate_role_fields(changes['role_fields'])
            result['description'], result['starting_scene'] = compatibility_fields(result['role_fields'])
    elif current.get('role_fields') is not None and any(
        key in changes and str(changes[key] or '').strip() != str(current.get(key) or '').strip()
        for key in ('description', 'starting_scene')
    ):
        result['role_fields'] = None
    if '_external_import' in current:
        result['_external_import'] = deepcopy(current['_external_import'])
    return result


def structured_projection(fields, name, *, detail=False):
    value = validate_role_fields(fields)
    keys = tuple(ROLE_LIMITS) if detail else ('description', 'personality', 'scenario', 'dialogue_examples')
    return {'name': name, 'semantics': ROLE_SEMANTICS, **{key: value[key] for key in keys}}
