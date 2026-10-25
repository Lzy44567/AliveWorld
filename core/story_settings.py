"""Per-story gameplay settings and legacy-save normalization."""

from copy import deepcopy
from core.story_direction import normalize_preference_emphasis

from core.story_experience import DEFAULT_STORY_EXPERIENCE, normalize_story_experience
from core.story_length import DEFAULT_TARGET_STORY_LENGTH, normalize_target_story_length, normalize_minimum_story_length


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
    "worldbookNotices": True,
    "worldbookDetailedNotices": False,
    "worldbookNoticeContent": False,
    "learnUserPreferences": True,
    "useUserPreferences": True,
    "preferenceEmphasis": "balanced",
    "deepPreferenceAnalysis": True,
    "analyzeSensitivePreferences": False,
    "preferenceStoryEnabled": True,
    "preferenceAdultEnabled": True,
    "preferenceActionEnabled": True,
    "preferenceCharacterEnabled": True,
    "preferenceRelationshipEnabled": True,
    "preferenceVisualEnabled": True,
    "storyExperiencePreset": DEFAULT_STORY_EXPERIENCE,
    "targetStoryLength": DEFAULT_TARGET_STORY_LENGTH,
    "minimumStoryLength": 0,
}


def normalize_story_settings(settings=None, defaults=None):
    normalized = deepcopy(DEFAULT_STORY_SETTINGS)
    for source in (defaults or {}, settings or {}):
        for key in normalized:
            if key not in source:
                continue
            if key == "targetStoryLength":
                normalized[key] = normalize_target_story_length(source[key])
            elif key == "minimumStoryLength":
                normalized[key] = source[key]
            elif key == "storyExperiencePreset":
                normalized[key] = normalize_story_experience(source[key])
            elif key == "preferenceEmphasis":
                normalized[key] = normalize_preference_emphasis(source[key])
            else:
                normalized[key] = bool(source[key])
    normalized["minimumStoryLength"] = normalize_minimum_story_length(normalized["minimumStoryLength"], normalized["targetStoryLength"])
    return normalized
