// src/store/gameStore.js
import { reactive } from 'vue';

export const gameStore = reactive({
  sessionId: null,
  currentSaveName: null, 
  isProcessing: false,
  
  chatLog: [],
  
  playerState: { hp: 100, maxHp: 100, mana: 100, maxMana: 100 },
  dynamicBars: {}, properties: {}, npcs: {}, buffs: {},
  
  aiSuggestions: [], 
  currentScene: { name: "未知界域", img: "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?q=80&w=400&auto=format&fit=crop" },
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
    // 【修复】将 Python 的 snake_case 完美映射到前端的 camelCase
    if (newState.player) {
      this.playerState = {
        hp: newState.player.hp || 0,
        maxHp: newState.player.max_hp || 100,
        mana: newState.player.mana || 0,
        maxMana: newState.player.max_mana || 100
      };
    }
    if (newState.bars) this.dynamicBars = newState.bars;
    if (newState.properties) this.properties = newState.properties;
    if (newState.npcs) this.npcs = newState.npcs;
    if (newState.buffs) this.buffs = newState.buffs;
  },

  reset() {
    this.sessionId = null;
    this.currentSaveName = null;
    this.chatLog = [];
    this.playerState = { hp: 100, maxHp: 100, mana: 100, maxMana: 100 };
    this.dynamicBars = {}; this.properties = {}; this.npcs = {}; this.buffs = {};
    this.companions = [];
  }
});