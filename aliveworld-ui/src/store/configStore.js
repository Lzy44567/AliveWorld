// src/store/configStore.js
import { reactive } from 'vue';

export const configStore = reactive({
  // 全局大模型与引擎设置
  globalSettings: {
    apiKey: "", 
    imageApiUrl: "http://127.0.0.1:8188"
  },
  
  // 局内调试与交互设置
  settings: {
    showFutures: true,      // 显示 n*N 折叠未来
    showDice: true,         // 显示掷骰结果
    allowReroll: true,      // 允许重置未来
    aiSuggestions: true,    // 开启灵感按钮
    autoImage: true         // 异步生图
  },
  
  // 跟随当前游玩存档的特定设置
  localSettings: { 
    showTime: null, 
    showMap: false, 
    plotCompass: "" 
  }
});