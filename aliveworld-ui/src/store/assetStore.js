// src/store/assetStore.js 完整替代参考

import { reactive } from 'vue';
import { assetApi } from '../api/assetApi';

export const assetStore = reactive({
  newSaveName: "",
  selectedStyle: "默认 (无)", 
  selectedWorldbook: "无界域 (暂不加载)",
  selectedPlayerPersona: "空白模板 (无名者)",

  availableWorldbooks: [],
  availableStyles: [],
  availableSaves: [], 
  
  saves: [],
  // 基础空容器
  characters: { local: [], global: [] },
  worlds: { local: [], global: [] },
  styles: { local: [], global: [] },
  entities: { local: [], global: [] }, // 预留实体库
  
  insertCharData: { name: "", entrance: "" },

  async fetchAssets() {
    try {
      const data = await assetApi.getAssets();
      this.availableWorldbooks = data.worldbooks || [];
      this.availableStyles = data.styles || [];
      this.availableSaves = data.saves || [];
      
      // 1. 映射保存数据
      this.saves = this.availableSaves.map(name => ({
        id: name, name: name, type: "Local", desc: "历史记忆节点..."
      }));

      // 2. 映射全局资产
      this.worlds.global = this.availableWorldbooks.map(name => ({ name, tags: ["世界书"], desc: "常驻世界法则与词条设定。" }));
      this.styles.global = this.availableStyles.map(name => ({ name, tags: ["文风卡"], desc: "AI 叙事风格与限制。" }));
      this.characters.global = (data.characters || []).map(name => ({ name, tags: ["角色卡"], desc: "人物外观与背景设定。" }));
      
      // 🚀 修复问题 3：将拉取到的全局实体填充进全局实体库
      this.entities.global = (data.entities || []).map(name => ({ name, tags: ["实体卡"], desc: "幕后实体的暗流动机与危机因果。" }));
      
    } catch (e) {
      console.error("无法连接到万象资产服务器", e);
    }
  },

  // 🚀 修复问题 4：当开启/载入游戏或者回合推进时，动态向后端查询并重刷“局内专属”资产
  async fetchLocalAssets(sessionId) {
    if (!sessionId) {
      this.worlds.local = [];
      this.styles.local = [];
      this.characters.local = [];
      this.entities.local = [];
      return;
    }
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/game/${sessionId}/local_assets`);
      if (res.ok) {
        const data = await res.json();
        this.worlds.local = data.worldbooks || [];
        this.styles.local = data.styles || [];
        this.characters.local = data.characters || [];
        this.entities.local = data.entities || [];
      }
    } catch (e) {
      console.warn("未能在当前运行时下提取局部资产切片", e);
    }
  }
});