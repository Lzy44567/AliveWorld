// src/store/assetStore.js
import { reactive } from 'vue';
import { assetApi } from '../api/assetApi';

export const assetStore = reactive({
  // 当前新建游戏选择的表单数据
  newSaveName: "",
  selectedStyle: "默认 (无)", 
  selectedWorldbook: "无界域 (暂不加载)",
  selectedPlayerPersona: "空白模板 (无名者)",

  // 从后端 API 拉取的真实下拉列表
  availableWorldbooks: [],
  availableStyles: [],
  availableSaves: [], // 原始字符串数组
  
  // 用于 UI 渲染的详细列表 (包含占位数据)
  saves: [],
  characters: { local: [], global: [{ name: "莉莉娅 (模板)", tags: ["法师"], desc: "高傲的冰系法师。" }] },
  worlds: { local: [], global: [] },
  styles: { local: [], global: [] },
  entities: { local: [], global: [] },
  
  insertCharData: { name: "", entrance: "" },

  // [新增] 去后端拉取最新资产数据
  async fetchAssets() {
    try {
      const data = await assetApi.getAssets();
      this.availableWorldbooks = data.worldbooks || [];
      this.availableStyles = data.styles || [];
      this.availableSaves = data.saves || [];
      
      // 把后端传来的纯文字存档名，包装成我们要的 UI 卡片格式
      this.saves = this.availableSaves.map(name => ({
        id: name, name: name, type: "Local", desc: "历史记忆节点..."
      }));
    } catch (e) {
      console.error("无法连接到万象资产服务器", e);
    }
  }
});