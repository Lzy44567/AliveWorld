// src/store/uiStore.js
import { reactive } from 'vue';

export const uiStore = reactive({
  leftDrawerOpen: true,
  rightDrawerOpen: true,
  rightTab: 'world', 
  assetScope: 'global', 

  modals: { 
    settings: false, gallery: false, terminal: false, newGame: false, insertChar: false,
    assetEditor: false 
  },
  
  // [修改] 丰富 editorData，加入结构化的 form 对象，方便 Vue 表单绑定
  editorData: { 
    type: '', name: '', content: '', isNew: false,
    form: {
      name: '', tags: [], desc: '', global_setting: '', starting_scene: '', entries: [],
      motive: '', status: ''
    }
  },
  
  tabTitles: {
    saves: "📂 时间线档案", character: "🎭 角色卡图鉴", world: "🌍 世界法则",
    style: "📜 文风指导卡", entity: "👾 暗流实体库", local_edit: "⚙️ 局内专属设定"
  }
});