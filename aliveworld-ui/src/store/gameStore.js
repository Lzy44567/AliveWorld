// src/store/gameStore.js
import { reactive } from 'vue';

export const gameStore = reactive({
  sessionId: null,
  currentSaveName: null, 
  isProcessing: false,
  chatLog: [],
  
  dynamicBars: {}, 
  properties: {}, 
  npcs: {}, 
  buffs: {},
  
  aiSuggestions: [], 
  currentScene: { 
    name: "未知界域", 
    img: "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?q=80&w=400&auto=format&fit=crop" 
  },
  mapNodes: [], 
  companions: [], 
  currentSpeakerSprite: "", 
  isSpeakerActive: false,

  formatContent(content) {
    if (!content) return "";
    if (Array.isArray(content)) return content;
    if (typeof content !== 'string') return JSON.stringify(content);
    return content.replace(/\\n/g, '\n');
  },

  syncState(newState) {
    if (!newState) return;
    
    // 🚀 修复 Buff 不显示的 Bug：使用扩展运算符强制触发 Vue 的深层响应式！
    if (newState.bars) this.dynamicBars = { ...newState.bars };
    if (newState.properties) this.properties = { ...newState.properties };
    if (newState.npcs) this.npcs = { ...newState.npcs };
    if (newState.buffs) this.buffs = { ...newState.buffs };
  },

  reset() {
    this.sessionId = null;
    this.currentSaveName = null;
    this.chatLog = [];
    this.dynamicBars = {}; 
    this.properties = {}; 
    this.npcs = {}; 
    this.buffs = {};
    this.companions = [];
  }
});