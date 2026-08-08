// src/store/configStore.js
import { computed, reactive, watch } from 'vue';
import { normalizeStorySettings } from '../utils/storySettings';

const savedConfig = JSON.parse(localStorage.getItem('aw_config')) || {};
const legacyEntityVisibility = savedConfig.settings?.entityVisibility;
const SYSTEM_CONFIG_URL = '/api/v1/game/system_config';

function persistableConfig(globalSettings, settings, uiPreferences) {
  const safeGlobalSettings = { ...globalSettings };
  delete safeGlobalSettings.apiKey;
  delete safeGlobalSettings.memoryApiKey;
  delete safeGlobalSettings.preferenceApiKey;
  return { globalSettings: safeGlobalSettings, settings, uiPreferences };
}

export const configStore = reactive({
  uiPreferences: {
    showAdvancedSettings: savedConfig.uiPreferences?.showAdvancedSettings === true
  },
  globalSettings: {
    apiKey: savedConfig.globalSettings?.apiKey || "", 
    apiKeyConfigured: false,
    apiReady: false,
    apiBaseUrl: savedConfig.globalSettings?.apiBaseUrl || "https://api.deepseek.com",
    model: savedConfig.globalSettings?.model || "deepseek-v4-flash",
    memoryApiKey: savedConfig.globalSettings?.memoryApiKey || "",
    memoryApiKeyConfigured: false,
    memoryApiBaseUrl: savedConfig.globalSettings?.memoryApiBaseUrl || "",
    memoryModel: savedConfig.globalSettings?.memoryModel || "",
    memoryContextLimit: savedConfig.globalSettings?.memoryContextLimit || 32768,
    preferenceApiKey: savedConfig.globalSettings?.preferenceApiKey || "",
    preferenceApiKeyConfigured: false,
    preferenceApiBaseUrl: savedConfig.globalSettings?.preferenceApiBaseUrl || "",
    preferenceModel: savedConfig.globalSettings?.preferenceModel || "",
    imageApiUrl: savedConfig.globalSettings?.imageApiUrl || "http://127.0.0.1:8188",
    imageCheckpoint: savedConfig.globalSettings?.imageCheckpoint || "",
    imageCheckpoints: savedConfig.globalSettings?.imageCheckpoints || [],
    imageModelProfiles: savedConfig.globalSettings?.imageModelProfiles || {},
    imageWorkflowId: savedConfig.globalSettings?.imageWorkflowId || "builtin_basic",
    imageNegativePrompt: savedConfig.globalSettings?.imageNegativePrompt || "text, watermark, blurry, low quality",
    imageStylePreference: savedConfig.globalSettings?.imageStylePreference || "",
    imagePresentationLevel: savedConfig.globalSettings?.imagePresentationLevel || "",
    imageWidth: savedConfig.globalSettings?.imageWidth || 768,
    imageHeight: savedConfig.globalSettings?.imageHeight || 768,
    imageCount: savedConfig.globalSettings?.imageCount || 1,
    imageSteps: savedConfig.globalSettings?.imageSteps || 20,
    imageCfg: savedConfig.globalSettings?.imageCfg || 7
  },
  
  settings: normalizeStorySettings({
    showFutures: savedConfig.settings?.showFutures ?? true,      
    showDice: savedConfig.settings?.showDice ?? true,         
    allowReroll: savedConfig.settings?.allowReroll ?? true,      
    aiSuggestions: savedConfig.settings?.aiSuggestions ?? true,    
    autoImage: savedConfig.settings?.autoImage ?? false,
    showTime: savedConfig.settings?.showTime ?? true,
    entitiesEnabled: savedConfig.settings?.entitiesEnabled ?? true,
    showEntityNames: savedConfig.settings?.showEntityNames ?? ['names', 'motives', 'full'].includes(legacyEntityVisibility),
    showEntityMotives: savedConfig.settings?.showEntityMotives ?? ['motives', 'full'].includes(legacyEntityVisibility),
    allowEntityEditing: savedConfig.settings?.allowEntityEditing ?? legacyEntityVisibility === 'full',
    showEntityBubbles: savedConfig.settings?.showEntityBubbles ?? Boolean(savedConfig.settings?.showEntityDebug && legacyEntityVisibility !== 'hidden'),
    autoCompressMemory: savedConfig.settings?.autoCompressMemory ?? false,
    worldbookCaptureEnabled: savedConfig.settings?.worldbookCaptureEnabled ?? true,
    worldbookCaptureReview: savedConfig.settings?.worldbookCaptureReview ?? false,
    learnUserPreferences: savedConfig.settings?.learnUserPreferences ?? true,
    useUserPreferences: savedConfig.settings?.useUserPreferences ?? true,
    deepPreferenceAnalysis: savedConfig.settings?.deepPreferenceAnalysis ?? true,
    analyzeSensitivePreferences: savedConfig.settings?.analyzeSensitivePreferences ?? false,
    preferenceStoryEnabled: savedConfig.settings?.preferenceStoryEnabled ?? true,
    preferenceAdultEnabled: savedConfig.settings?.preferenceAdultEnabled ?? true,
    preferenceActionEnabled: savedConfig.settings?.preferenceActionEnabled ?? true,
    preferenceCharacterEnabled: savedConfig.settings?.preferenceCharacterEnabled ?? true,
    preferenceRelationshipEnabled: savedConfig.settings?.preferenceRelationshipEnabled ?? true,
    preferenceVisualEnabled: savedConfig.settings?.preferenceVisualEnabled ?? true
  }),
  
  story: {
    active: false, worldPremise: "", plotCompass: "",
    settings: normalizeStorySettings()
  },

  applyStoryConfig(data = {}) {
    this.story.active = true;
    this.story.worldPremise = data.world_premise ?? data.description ?? "";
    this.story.plotCompass = data.plot_compass ?? "";
    this.story.settings = normalizeStorySettings(data.story_settings, this.settings);
  },

  resetStoryConfig() {
    this.story.active = false;
    this.story.worldPremise = "";
    this.story.plotCompass = "";
    this.story.settings = normalizeStorySettings({}, this.settings);
  },

  restoreStoryDefaults() {
    this.story.settings = normalizeStorySettings({}, this.settings);
  },

  async syncToBackend() {
    try {
      const response = await fetch(SYSTEM_CONFIG_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.globalSettings)
      });
      if (response.ok) {
        if (this.globalSettings.apiKey.trim()) this.globalSettings.apiKeyConfigured = true;
        if (this.globalSettings.apiBaseUrl.trim() && this.globalSettings.model.trim()) {
          this.globalSettings.apiReady = true;
        }
        if (this.globalSettings.memoryApiKey.trim()) this.globalSettings.memoryApiKeyConfigured = true;
        if (this.globalSettings.preferenceApiKey.trim()) this.globalSettings.preferenceApiKeyConfigured = true;
        return true;
      }
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || '保存 API 配置失败');
    } catch (e) {
      console.error("同步配置失败", e);
      throw e;
    }
  },

  async fetchFromBackend() {
    try {
      const res = await fetch(SYSTEM_CONFIG_URL);
      if (res.ok) {
        const data = await res.json();
        if (data.apiKey) this.globalSettings.apiKey = data.apiKey;
        this.globalSettings.apiKeyConfigured = Boolean(data.apiKeyConfigured || this.globalSettings.apiKey);
        this.globalSettings.apiReady = Boolean(data.apiReady ?? this.globalSettings.apiKeyConfigured);
        if (data.apiBaseUrl) this.globalSettings.apiBaseUrl = data.apiBaseUrl;
        if (data.model) this.globalSettings.model = data.model;
        if (data.memoryApiKey) this.globalSettings.memoryApiKey = data.memoryApiKey;
        this.globalSettings.memoryApiKeyConfigured = Boolean(data.memoryApiKeyConfigured || this.globalSettings.memoryApiKey);
        this.globalSettings.memoryApiBaseUrl = data.memoryApiBaseUrl ?? this.globalSettings.memoryApiBaseUrl;
        this.globalSettings.memoryModel = data.memoryModel ?? this.globalSettings.memoryModel;
        this.globalSettings.memoryContextLimit = data.memoryContextLimit ?? this.globalSettings.memoryContextLimit;
        if (data.preferenceApiKey) this.globalSettings.preferenceApiKey = data.preferenceApiKey;
        this.globalSettings.preferenceApiKeyConfigured = Boolean(data.preferenceApiKeyConfigured || this.globalSettings.preferenceApiKey);
        this.globalSettings.preferenceApiBaseUrl = data.preferenceApiBaseUrl ?? this.globalSettings.preferenceApiBaseUrl;
        this.globalSettings.preferenceModel = data.preferenceModel ?? this.globalSettings.preferenceModel;
        this.globalSettings.imageApiUrl = data.imageApiUrl ?? this.globalSettings.imageApiUrl;
        return true;
      }
    } catch (e) { console.error("读取配置失败", e); }
    return false;
  }
});

export const effectiveStorySettings = computed(() =>
  configStore.story.active ? configStore.story.settings : configStore.settings
);

// 启动流程等待后端配置返回后，再判断是否需要首次 API 引导。
export const configReady = configStore.fetchFromBackend();

export async function waitForSystemConfig({ attempts = 8, delayMs = 500 } = {}) {
  let loaded = await configReady;
  for (let attempt = 1; !loaded && attempt < attempts; attempt += 1) {
    await new Promise(resolve => window.setTimeout(resolve, delayMs));
    loaded = await configStore.fetchFromBackend();
  }
  return loaded;
}

watch(() => configStore.globalSettings, () => {
  localStorage.setItem('aw_config', JSON.stringify(persistableConfig(configStore.globalSettings, configStore.settings, configStore.uiPreferences)));
}, { deep: true });

watch(() => configStore.settings, () => {
  localStorage.setItem('aw_config', JSON.stringify(persistableConfig(configStore.globalSettings, configStore.settings, configStore.uiPreferences)));
}, { deep: true });

watch(() => configStore.uiPreferences, () => {
  localStorage.setItem('aw_config', JSON.stringify(persistableConfig(configStore.globalSettings, configStore.settings, configStore.uiPreferences)));
}, { deep: true });
