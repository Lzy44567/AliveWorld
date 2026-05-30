// src/store/uiStore.js
import { reactive } from 'vue';

export const uiStore = reactive({
  leftDrawerOpen: true,
  rightDrawerOpen: true,
  rightTab: 'world', // 当前打开的右侧资产标签页
  assetScope: 'global', // 'local' 或 'global'

  // 全局弹窗状态
  modals: { 
    settings: false, 
    gallery: false, 
    terminal: false, 
    newGame: false, 
    insertChar: false 
  },
  
  // 右侧面板标题映射
  tabTitles: {
    saves: "📂 时间线档案", character: "🎭 角色卡图鉴", world: "🌍 世界法则",
    style: "📜 文风指导卡", entity: "👾 暗流实体库", memory: "🧠 记忆与偏好", local_edit: "⚙️ 局内专属设定"
  }
});