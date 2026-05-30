// src/store/gameStore.js
import { reactive } from 'vue';

export const gameStore = reactive({
  sessionId: null,
  isProcessing: false,
  
  // 核心推演日志
  chatLog: [],
  
  // 动态状态条与属性
  playerState: { hp: 100, maxHp: 100 },
  dynamicBars: {}, 
  properties: {}, 
  npcs: {}, 
  buffs: {},
  
  // 灵感提示语
  aiSuggestions: ["调查地上的血迹", "质问旁边的酒馆老板", "悄悄离开这里"], 

  // 视觉/多模态占位数据
  currentScene: { name: "旧城区废墟", img: "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?q=80&w=400&auto=format&fit=crop" },
  mapNodes: [
    { id: 1, name: "酒馆", type: "safe", status: "visited" },
    { id: 2, name: "废墟", type: "event", status: "current" }
  ],
  companions: [ 
    { name: "莉莉娅", avatar: "👩🏼‍🦳", hp: 80, maxHp: 100, status: "衣服: 破损严重，露出白皙的肩膀。状态: 极度警惕。" } 
  ], 
  currentSpeakerSprite: "https://images.unsplash.com/photo-1542204625-236b284e366d?q=80&w=400&auto=format&fit=crop", 
  isSpeakerActive: true,

  // 格式化文本助手方法 (用于处理 \n 换行)
  formatContent(content) {
    if (!content) return "";
    if (Array.isArray(content)) return content;
    if (typeof content !== 'string') return JSON.stringify(content);
    return content.replace(/\\n/g, '\n');
  },

  // 状态同步更新方法
  syncState(newState) {
    if (!newState) return;
    if (newState.player) this.playerState = newState.player;
    if (newState.bars) this.dynamicBars = newState.bars;
    if (newState.properties) this.properties = newState.properties;
    if (newState.npcs) this.npcs = newState.npcs;
    if (newState.buffs) this.buffs = newState.buffs;
  }
});