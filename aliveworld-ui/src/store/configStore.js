// src/store/configStore.js
// 100% 完整底稿 (请直接覆盖原文件)

import { reactive, watch } from 'vue';

// 🚀 从浏览器本地缓存读取持久化配置
const savedConfig = JSON.parse(localStorage.getItem('aw_config')) || {};

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
    
    // 🚀 新增占位配置
    showTime: savedConfig.settings?.showTime ?? true,
    showEntityDebug: savedConfig.settings?.showEntityDebug ?? true,
    autoCompressMemory: savedConfig.settings?.autoCompressMemory ?? false
  },
  
  localSettings: { 
    showTime: null, 
    showMap: false, 
    plotCompass: "" 
  }
});

// 🚀 监听变动并写入 localStorage
watch(() => configStore, (newVal) => {
  localStorage.setItem('aw_config', JSON.stringify({
    globalSettings: newVal.globalSettings,
    settings: newVal.settings
  }));
}, { deep: true });