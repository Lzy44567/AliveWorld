// src/store/uiStore.js
// 100% 完整底稿

import { reactive } from 'vue';

export const uiStore = reactive({
  leftDrawerOpen: true,
  rightDrawerOpen: true,
  rightTab: 'world', 
  assetScope: 'global', 

  modals: { 
    settings: false, gallery: false, terminal: false, newGame: false, insertChar: false,
    assetEditor: false, worldbookWorkshop: false
  },
  workshopWorldbookName: '',
  
  editorData: { 
    type: '', name: '', content: '', isNew: false,
    form: {
      name: '', tags: [], desc: '', overview: '', axiomsText: '', starting_scene: '', entries: [],
      motive: '', status: '', is_active: true, is_player: false
    }
  },
  
  tabTitles: {
    saves: "📂 时间线档案", character: "🎭 角色卡图鉴", world: "🌍 世界法则",
    style: "📜 文风指导卡", entity: "👾 暗流实体库", local_edit: "⚙️ 局内专属设定"
  },

  // 🚀 问题 4：新增全局非阻断式飘字提示
  toast: { show: false, message: "", type: "success" },
  
  showToast(message, type = "success") {
    this.toast.message = message;
    this.toast.type = type;
    this.toast.show = true;
    setTimeout(() => { this.toast.show = false; }, 3000);
  }
});
