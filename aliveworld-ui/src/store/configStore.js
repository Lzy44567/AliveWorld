// src/store/configStore.js
import { reactive, watch } from 'vue';

const savedConfig = JSON.parse(localStorage.getItem('aw_config')) || {};
const legacyEntityVisibility = savedConfig.settings?.entityVisibility;

export const configStore = reactive({
  globalSettings: {
    apiKey: savedConfig.globalSettings?.apiKey || "", 
    apiBaseUrl: savedConfig.globalSettings?.apiBaseUrl || "https://api.openai.com/v1",
    model: savedConfig.globalSettings?.model || "gpt-3.5-turbo",
    imageApiUrl: savedConfig.globalSettings?.imageApiUrl || "http://127.0.0.1:8188"
  },
  
  settings: {
    showFutures: savedConfig.settings?.showFutures ?? true,      
    showDice: savedConfig.settings?.showDice ?? true,         
    allowReroll: savedConfig.settings?.allowReroll ?? true,      
    aiSuggestions: savedConfig.settings?.aiSuggestions ?? true,    
    autoImage: savedConfig.settings?.autoImage ?? true,
    showTime: savedConfig.settings?.showTime ?? true,
    showEntityNames: savedConfig.settings?.showEntityNames ?? ['names', 'motives', 'full'].includes(legacyEntityVisibility),
    showEntityMotives: savedConfig.settings?.showEntityMotives ?? ['motives', 'full'].includes(legacyEntityVisibility),
    allowEntityEditing: savedConfig.settings?.allowEntityEditing ?? legacyEntityVisibility === 'full',
    showEntityBubbles: savedConfig.settings?.showEntityBubbles ?? Boolean(savedConfig.settings?.showEntityDebug && legacyEntityVisibility !== 'hidden'),
    autoCompressMemory: savedConfig.settings?.autoCompressMemory ?? false
  },
  
  localSettings: { showTime: null, showMap: false, plotCompass: "" },

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
      }
    } catch (e) { console.error("读取配置失败", e); }
  }
});

// 网页启动时从后端拉取一次最新配置（以防后端是被其他人改动的）
configStore.fetchFromBackend();

watch(() => configStore.globalSettings, () => {
  localStorage.setItem('aw_config', JSON.stringify({ globalSettings: configStore.globalSettings, settings: configStore.settings }));
  configStore.syncToBackend(); // ✨ 实时将修改的 API Key 等拍入后端 config.yml
}, { deep: true });

watch(() => configStore.settings, () => {
  localStorage.setItem('aw_config', JSON.stringify({ globalSettings: configStore.globalSettings, settings: configStore.settings }));
}, { deep: true });
