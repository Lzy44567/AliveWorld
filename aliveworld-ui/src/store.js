// src/store.js
import { reactive } from 'vue'

export const store = reactive({
  sessionId: null,
  isProcessing: false,
  
  // ================= UI 布局状态 =================
  leftDrawerOpen: true,
  rightDrawerOpen: true,
  rightTab: 'world', 
  assetScope: 'global', 
  
  // 弹窗状态管理
  modals: { settings: false, gallery: false, terminal: false, newGame: false, insertChar: false },
  insertCharData: { name: "", entrance: "" }, // 中途登场角色的表单数据

  // ================= 游戏设置 =================
  settings: {
    showTime: false,        
    showFutures: true,      
    showDice: true,         
    allowReroll: true,      
    aiSuggestions: true,    
    autoImage: true,        
    apiKey: "", imageApiUrl: "http://127.0.0.1:8188"
  },
  
  // 局内独立设置 (跟随故事线存档)
  localSettings: { 
    showTime: null, 
    showMap: false, // 默认关闭地图
    plotCompass: "" // 剧情发展指导，从主界面移入此处
  },

  // ================= 核心推演状态 =================
  chatLog: [],
  playerState: { hp: 100, maxHp: 100 },
  properties: {}, npcs: {}, dynamicBars: {}, buffs: {},
  aiSuggestions: ["调查地上的血迹", "质问旁边的酒馆老板", "悄悄离开这里"], 

  // ================= 视觉占位 =================
  currentScene: { name: "旧城区废墟", img: "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?q=80&w=400&auto=format&fit=crop" },
  mapNodes: [
    { id: 1, name: "酒馆", type: "safe", status: "visited" },
    { id: 2, name: "废墟", type: "event", status: "current" }
  ],
  companions: [ 
    // 扩展了描述空间，展示衣服破损等状态
    { name: "莉莉娅", avatar: "👩🏼‍🦳", hp: 80, maxHp: 100, status: "衣服: 破损严重，露出白皙的肩膀。状态: 极度警惕。" } 
  ], 
  currentSpeakerSprite: "https://images.unsplash.com/photo-1542204625-236b284e366d?q=80&w=400&auto=format&fit=crop", 
  isSpeakerActive: true,

  // ================= 资产卡片库占位 =================
  saves: [
    { id: "s1", name: "深渊季：陨落", date: "2026-05-30", type: "AutoSave", desc: "刚进入地下城第二层..." },
    { id: "s2", name: "测试存档", date: "2026-05-29", type: "Manual", desc: "测试战斗与立绘。" }
  ],
  characters: {
    local: [{ name: "莉莉娅", tags: ["傲娇", "队友"], desc: "在废墟中被玩家救下。" }],
    global: [{ name: "莉莉娅 (模板)", tags: ["法师"], desc: "高傲的冰系法师。" }, { name: "神秘商人", tags: ["NPC"], desc: "总是在奇怪的地方卖高价药水。" }]
  },
  worlds: {
    local: [],
    global: [{ name: "赛博新神", tags: ["科幻"], desc: "财阀统治的霓虹都市。" }, { name: "克苏鲁深渊", tags: ["恐怖"], desc: "理智是消耗品。" }]
  },
  styles: { local: [], global: [{ name: "硬核跑团", tags: ["残酷"], desc: "死亡率极高。" }, { name: "轻小说", tags: ["轻松"], desc: "充满吐槽。" }] },
  entities: {
    local: [{ name: "机械教廷", motive: "追杀玩家", status: "调集中", desc: "因玩家炸毁基站而结仇。" }],
    global: [{ name: "世界意志", motive: "维持平衡", status: "沉睡", desc: "当极度混乱时降下天罚。" }]
  },

  // 临时选中的选项
  selectedStyle: "默认 (无)", 
  selectedWorldbook: "无界域 (暂不加载)",
  selectedPlayerPersona: "空白模板 (无名者)", // 玩家扮演角色卡

  // 资产类别标题映射
  tabTitles: {
    saves: "📂 时间线档案", character: "🎭 角色卡图鉴", world: "🌍 世界法则",
    style: "📜 文风指导卡", entity: "👾 暗流实体库", memory: "🧠 记忆与偏好", local_edit: "⚙️ 局内专属设定"
  },

  formatContent(content) {
    if (!content) return ""
    if (Array.isArray(content)) return content
    if (typeof content !== 'string') return JSON.stringify(content)
    return content.replace(/\\n/g, '\n')
  }
})