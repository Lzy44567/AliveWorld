// src/store/configStore.js
import { computed, reactive, watch } from 'vue';
import { normalizeStorySettings } from '../utils/storySettings';

const savedConfig = JSON.parse(localStorage.getItem('aw_config')) || {};
const legacyEntityVisibility = savedConfig.settings?.entityVisibility;

export const configStore = reactive({
  globalSettings: {
    apiKey: savedConfig.globalSettings?.apiKey || "", 
    apiBaseUrl: savedConfig.globalSettings?.apiBaseUrl || "https://api.openai.com/v1",
    model: savedConfig.globalSettings?.model || "gpt-3.5-turbo",
    memoryApiKey: savedConfig.globalSettings?.memoryApiKey || "",
    memoryApiBaseUrl: savedConfig.globalSettings?.memoryApiBaseUrl || "",
    memoryModel: savedConfig.globalSettings?.memoryModel || "",
    memoryContextLimit: savedConfig.globalSettings?.memoryContextLimit || 32768,
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
    useUserPreferences: savedConfig.settings?.useUserPreferences ?? true
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
      await fetch('http://127.0.0.1:8000/api/v1/game/system_config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.globalSettings)
      });
    } catch (e) { console.error("同步配置失败", e); }
  },

  async fetchFromBackend() {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/game/system_config');
      if (res.ok) {
        const data = await res.json();
        if (data.apiKey) this.globalSettings.apiKey = data.apiKey;
        if (data.apiBaseUrl) this.globalSettings.apiBaseUrl = data.apiBaseUrl;
        if (data.model) this.globalSettings.model = data.model;
        this.globalSettings.memoryApiKey = data.memoryApiKey ?? this.globalSettings.memoryApiKey;
        this.globalSettings.memoryApiBaseUrl = data.memoryApiBaseUrl ?? this.globalSettings.memoryApiBaseUrl;
        this.globalSettings.memoryModel = data.memoryModel ?? this.globalSettings.memoryModel;
        this.globalSettings.memoryContextLimit = data.memoryContextLimit ?? this.globalSettings.memoryContextLimit;
      }
    } catch (e) { console.error("读取配置失败", e); }
  }
});

export const effectiveStorySettings = computed(() =>
  configStore.story.active ? configStore.story.settings : configStore.settings
);

// 网页启动时从后端拉取一次最新配置（以防后端是被其他人改动的）
configStore.fetchFromBackend();

watch(() => configStore.globalSettings, () => {
  localStorage.setItem('aw_config', JSON.stringify({ globalSettings: configStore.globalSettings, settings: configStore.settings }));
  configStore.syncToBackend(); // ✨ 实时将修改的 API Key 等拍入后端 config.yml
}, { deep: true });

watch(() => configStore.settings, () => {
  localStorage.setItem('aw_config', JSON.stringify({ globalSettings: configStore.globalSettings, settings: configStore.settings }));
}, { deep: true });
