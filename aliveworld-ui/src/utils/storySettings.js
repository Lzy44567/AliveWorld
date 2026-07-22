export const STORY_SETTING_DEFAULTS = Object.freeze({
  showFutures: true, showDice: true, allowReroll: true, aiSuggestions: true,
  entitiesEnabled: true, showEntityNames: false, showEntityMotives: false,
  allowEntityEditing: false, showEntityBubbles: false, showTime: true,
  showInfluenceBubbles: false,
  showCausalLedger: false,
  autoCompressMemory: false,
  worldbookCaptureEnabled: true,
  worldbookCaptureReview: false,
  learnUserPreferences: true,
  useUserPreferences: true,
  deepPreferenceAnalysis: true,
  analyzeSensitivePreferences: false,
  preferenceStoryEnabled: true,
  preferenceAdultEnabled: true,
  preferenceActionEnabled: true,
  preferenceCharacterEnabled: true,
  preferenceRelationshipEnabled: true,
  preferenceVisualEnabled: true
});

export function normalizeStorySettings(settings = {}, defaults = STORY_SETTING_DEFAULTS) {
  return Object.fromEntries(Object.keys(STORY_SETTING_DEFAULTS).map(key => [
    key, Boolean(settings[key] ?? defaults[key] ?? STORY_SETTING_DEFAULTS[key])
  ]));
}
