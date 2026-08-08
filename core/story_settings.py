"""Per-story gameplay settings and legacy-save normalization."""

from copy import deepcopy

from core.story_length import DEFAULT_TARGET_STORY_LENGTH, normalize_target_story_length


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
    "learnUserPreferences": True,
    "useUserPreferences": True,
    "deepPreferenceAnalysis": True,
    "analyzeSensitivePreferences": False,
    "preferenceStoryEnabled": True,
    "preferenceAdultEnabled": True,
    "preferenceActionEnabled": True,
    "preferenceCharacterEnabled": True,
    "preferenceRelationshipEnabled": True,
    "preferenceVisualEnabled": True,
    "targetStoryLength": DEFAULT_TARGET_STORY_LENGTH,
}


def normalize_story_settings(settings=None, defaults=None):
    normalized = deepcopy(DEFAULT_STORY_SETTINGS)
    for source in (defaults or {}, settings or {}):
        for key in normalized:
            if key not in source:
                continue
            if key == "targetStoryLength":
                normalized[key] = normalize_target_story_length(source[key])
            else:
                normalized[key] = bool(source[key])
    return normalized
