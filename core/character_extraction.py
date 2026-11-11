"""Independent role-card drafts, excluding story-owned state."""
from copy import deepcopy
from core.asset_lifecycle import normalize_asset_name
from core.character_profiles import coordinate_character_write
from core.world_packages.identity import assign_new_asset_id

PROFILE_FIELDS = ('description', 'appearance', 'personality', 'starting_scene',
                  'dialogue_examples', 'role_fields')


def npc_sources(records):
    """Identity, not name, owns an extraction candidate (including departed NPCs)."""
    return [{'id': record['id'], 'name': record['name'],
             'aliases': list(record['aliases']), 'status': record.get('last_status', '')}
            for record in records.values()]


def selected_evidence(turns, selected_ids):
    """Only explicit public story selections; no ledger or discarded attempts."""
    by_id = {turn['turn_id']: turn for turn in turns}
    if len(set(selected_ids)) != len(selected_ids) or any(i not in by_id for i in selected_ids):
        raise ValueError('所选回合已撤回、移除或重复，请重新选择')
    return [{'turn_id': i, 'player': by_id[i].get('player', ''),
             'story': by_id[i].get('story', '')} for i in selected_ids]


def prepare_character_card(profile, name):
    """Project an explicitly selected profile, not its source story aggregate."""
    fields = {key: deepcopy(profile[key]) for key in PROFILE_FIELDS if key in profile}
    for key, value in fields.items():
        if key != 'role_fields' and not isinstance(value, str):
            raise ValueError(f'{key} 必须是文本')
    card = coordinate_character_write({}, fields)
    card.update(name=normalize_asset_name(name), is_player=False, is_active=True, tags=[])
    assign_new_asset_id(card)
    return card
