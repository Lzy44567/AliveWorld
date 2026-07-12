"""Per-story gameplay settings and legacy-save normalization."""

from copy import deepcopy


DEFAULT_STORY_SETTINGS = {
    "showFutures": True,
    "showDice": True,
    "allowReroll": True,
    "aiSuggestions": True,
    "entitiesEnabled": True,
    "showEntityNames": False,
    "showEntityMotives": False,
    "allowEntityEditing": False,
    "showEntityBubbles": False,
    "showInfluenceBubbles": False,
    "showCausalLedger": False,
    "showTime": True,
    "autoCompressMemory": False,
    "worldbookCaptureEnabled": True,
    "worldbookCaptureReview": False,
}


def normalize_story_settings(settings=None, defaults=None):
    normalized = deepcopy(DEFAULT_STORY_SETTINGS)
    for source in (defaults or {}, settings or {}):
        for key in normalized:
            if key in source:
                normalized[key] = bool(source[key])
    return normalized
