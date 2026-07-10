// src/store/assetStore.js
// 100% 完整物理读写底稿 (请直接覆盖原文件)

import { reactive } from 'vue';
import { assetApi } from '../api/assetApi';

export const assetStore = reactive({
  newSaveName: "",
  selectedStyle: "默认 (无)", 
  selectedWorldbook: "无界域 (暂不加载)",
  selectedPlayerPersona: "空白模板 (无名者)", // 🚀 问题 3

  availableWorldbooks: [],
  availableStyles: [],
  availableSaves: [], 
  
  saves: [],
  // 提前准备好空容器
  characters: { local: [], global: [] },
  worlds: { local: [], global: [] },
  styles: { local: [], global: [] },
  entities: { local: [], global: [] },
  
  insertCharData: { name: "", entrance: "" },

  makeGlobalAssets(names, metadata, defaultTag, defaultDescription) {
    const metaByName = new Map((metadata || []).map(item => [item.name, item]));
    return names.map(name => {
      const meta = metaByName.get(name) || {};
      const tags = Array.isArray(meta.tags) && meta.tags.length ? [...meta.tags] : [defaultTag];
      if (meta.is_template && !tags.includes('模板')) tags.unshift('模板');
      return { name, tags, desc: meta.description || defaultDescription, is_template: Boolean(meta.is_template) };
    });
  },

  async fetchAssets() {
    try {
      const data = await assetApi.getAssets();
      this.availableWorldbooks = data.worldbooks || [];
      this.availableStyles = data.styles || [];
      this.availableSaves = data.saves || [];
      
      // 1. 映射存档列表
      this.saves = this.availableSaves.map(name => ({
        id: name, name: name, type: "Local", desc: "历史记忆节点..."
      }));

      // 2. 映射全局资产
      const metadata = data.asset_meta || {};
      this.worlds.global = this.makeGlobalAssets(this.availableWorldbooks, metadata.worldbooks, "世界书", "常驻世界法则与词条设定。");
      this.styles.global = this.makeGlobalAssets(this.availableStyles, metadata.styles, "文风卡", "AI 叙事风格与限制。");
      this.characters.global = this.makeGlobalAssets(data.characters || [], metadata.characters, "角色卡", "人物外观与背景设定。");
      this.entities.global = this.makeGlobalAssets(data.entities || [], metadata.entities, "实体卡", "幕后实体的暗流动机与危机因果。");
      
    } catch (e) {
      console.error("无法连接到万象资产服务器", e);
    }
  },

  // 🚀 问题 4：动态向后端查询并重刷“局内专属”资产
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
