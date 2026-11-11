"""Explicit portable memories; never mutate the reusable source card."""
from copy import deepcopy
from core.character_profiles import coordinate_character_write

KEY = 'portable_experiences'


def with_experiences(card, text, source_world):
    result = deepcopy(card)
    if not isinstance(text, str) or not isinstance(source_world, str):
        raise ValueError('经历与来源世界必须是文本')
    result.pop(KEY, None)
    if text.strip():
        result[KEY] = {'source_world': source_world, 'summary': text.strip()}
    return result


def for_destination(card, *, include_experiences=False):
    result = deepcopy(card)
    experience = result.pop(KEY, None)
    if not include_experiences or not experience:
        return result
    if not isinstance(experience, dict) or not all(isinstance(experience.get(k), str) for k in ('source_world', 'summary')):
        raise ValueError('角色携带经历格式错误，请先编辑角色卡')
    section = ('【角色携带的旧世界经历】\n来源：' + experience['source_world'] + '\n' + experience['summary']
               + '\n这是角色记得的来源世界经历，不是目标世界历史；同名人物不是自动认识的旧友。能力遵循目标世界规则。')
    if result.get('role_fields'):
        fields = deepcopy(result['role_fields'])
        fields['scenario'] = (fields['scenario'] + '\n\n' + section).strip()
        return coordinate_character_write(result, {'role_fields': fields})
    result['description'] = (result.get('description', '') + '\n\n' + section).strip()
    return result
