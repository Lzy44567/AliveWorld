"""Independent role-card drafts, excluding story-owned state."""
from copy import deepcopy
from core.asset_lifecycle import normalize_asset_name
from core.character_profiles import coordinate_character_write
from core.world_packages.identity import assign_new_asset_id

PROFILE_FIELDS = ('description', 'appearance', 'personality', 'starting_scene',
                  'dialogue_examples', 'role_fields')


def prepare_character_card(profile, name):
    """Project an explicitly selected profile, not its source story aggregate."""
    fields = {key: deepcopy(profile[key]) for key in PROFILE_FIELDS if key in profile}
    card = coordinate_character_write({}, fields)
    card.update(name=normalize_asset_name(name), is_player=False, is_active=True, tags=[])
    assign_new_asset_id(card)
    return card
