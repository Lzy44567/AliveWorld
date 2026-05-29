<!-- aliveworld-ui/src/components/Lobby.vue -->
<script setup>
import { ref, onMounted } from 'vue'
import { store } from '../store.js'

// 导航菜单：'hub' (冒险枢纽), 'workshop' (万象工坊), 'logs' (系统终端)
const currentMenu = ref('hub')
// 工坊子菜单：'character', 'worldbook', 'style', 'entity'
const workshopTab = ref('character')

// 冒险枢纽数据
const newSaveName = ref("")
const showNewGamePanel = ref(false) // 是否显示新建游戏面板

onMounted(async () => {
  await store.fetchAssets()
})

// === 真实的 API 调用逻辑 (保持不变) ===
const startGame = async () => {
  if (!newSaveName.value.trim()) { alert("⚠️ 命运必须有一个名字 (存档名为空)！"); return }
  store.isProcessing = true
  try {
    const response = await fetch("http://127.0.0.1:8000/api/v1/game/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ style_name: store.selectedStyle, worldbook_name: store.selectedWorldbook, save_name: newSaveName.value })
    })
    if (!response.ok) { alert("创世失败"); return }
    const data = await response.json()
    store.sessionId = data.session_id; store.chatLog = data.chat_messages; store.syncState(data.state)
    store.isInLobby = false
  } catch (err) { alert("服务器未响应") } finally { store.isProcessing = false }
}

const loadGame = async (saveName) => {
  store.isProcessing = true
  try {
    const response = await fetch("http://127.0.0.1:8000/api/v1/game/load", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ save_name: saveName })
    })
    if (!response.ok) { alert("存档已损坏！"); return }
    const data = await response.json()
    store.sessionId = data.session_id; store.chatLog = data.chat_messages || []; store.syncState(data.state)
    store.selectedStyle = data.style_name; store.selectedWorldbook = data.worldbook_name
    store.isInLobby = false
  } catch (err) { alert("网络连接中断") } finally { store.isProcessing = false }
}

// 占位功能：删除存档
const deleteSave = (saveName) => {
  if(confirm(`警告：确定要彻底粉碎【${saveName}】的时间线吗？`)) {
    alert("（UI占位符）这将在未来调用后端的删除 API！")
  }
}
</script>

<template>
  <div class="h-full w-full flex bg-aw_bg text-slate-200">
    
    <!-- 左侧主导航栏 -->
    <nav class="w-64 bg-aw_panel border-r border-slate-700 flex flex-col shadow-2xl z-10">
      <div class="p-6 border-b border-slate-700 bg-slate-900/50">
        <h1 class="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-indigo-400 tracking-wider">AliveWorld</h1>
        <p class="text-xs text-slate-400 mt-2 font-mono">v2.0 UI Mockup</p>
      </div>
      
      <div class="flex-1 p-4 space-y-2">
        <button @click="currentMenu = 'hub'" :class="currentMenu === 'hub' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/50' : 'hover:bg-slate-800 text-slate-400'" class="w-full flex items-center gap-3 px-4 py-3 rounded-xl font-bold transition">
          <span class="text-xl">🌌</span> 冒险枢纽
        </button>
        <button @click="currentMenu = 'workshop'" :class="currentMenu === 'workshop' ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-900/50' : 'hover:bg-slate-800 text-slate-400'" class="w-full flex items-center gap-3 px-4 py-3 rounded-xl font-bold transition">
          <span class="text-xl">🛠️</span> 万象工坊
        </button>
        <button @click="currentMenu = 'logs'" :class="currentMenu === 'logs' ? 'bg-rose-600 text-white shadow-lg shadow-rose-900/50' : 'hover:bg-slate-800 text-slate-400'" class="w-full flex items-center gap-3 px-4 py-3 rounded-xl font-bold transition">
          <span class="text-xl">💻</span> 系统终端
        </button>
      </div>
    </nav>

    <!-- 右侧内容展示区 -->
    <main class="flex-1 overflow-y-auto bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] relative">
      
      <!-- ================= 页面 1：冒险枢纽 (Hub) ================= -->
      <div v-if="currentMenu === 'hub'" class="p-8 max-w-7xl mx-auto animate-[fadeIn_0.3s_ease-out]">
        
        <div class="flex justify-between items-end mb-8 border-b border-slate-700 pb-4">
          <div>
            <h2 class="text-3xl font-bold text-slate-100">命运十字路口</h2>
            <p class="text-slate-400 mt-2">选择一段历史，或是创造一个新的界域。</p>
          </div>
          <button v-if="!showNewGamePanel" @click="showNewGamePanel = true" class="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 rounded-lg font-bold text-white shadow-lg transition flex items-center gap-2">
            <span>✨</span> 新启篇章
          </button>
        </div>

        <!-- 新建游戏折叠面板 -->
        <div v-if="showNewGamePanel" class="bg-slate-800/80 border border-emerald-500/30 p-6 rounded-2xl mb-8 shadow-xl relative backdrop-blur-sm">
          <button @click="showNewGamePanel = false" class="absolute top-4 right-4 text-slate-400 hover:text-white">✕ 关闭</button>
          <h3 class="text-xl font-bold text-emerald-400 mb-6">✨ 编织新命运</h3>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <div><label class="text-sm font-bold text-slate-400 mb-2 block">📝 冒险命名 (必填)</label><input v-model="newSaveName" class="w-full bg-slate-900/80 border border-slate-600 rounded-lg p-3 text-white focus:border-emerald-500 outline-none" placeholder="例如：深渊季" /></div>
            <div><label class="text-sm font-bold text-slate-400 mb-2 block">🌍 选择世界书</label><select v-model="store.selectedWorldbook" class="w-full bg-slate-900/80 border border-slate-600 rounded-lg p-3 text-white focus:border-emerald-500 outline-none"><option>无界域 (暂不加载)</option><option v-for="wb in store.availableWorldbooks" :key="wb" :value="wb">{{ wb }}</option></select></div>
            <div><label class="text-sm font-bold text-slate-400 mb-2 block">🎭 选择文风卡</label><select v-model="store.selectedStyle" class="w-full bg-slate-900/80 border border-slate-600 rounded-lg p-3 text-white focus:border-emerald-500 outline-none"><option>默认 (无)</option><option v-for="style in store.availableStyles" :key="style" :value="style">{{ style }}</option></select></div>
          </div>
          <!-- 角色卡选择将在未来替换这里的 UI -->
          <div class="text-xs text-slate-500 mb-6 italic">注：在 V2 完整版中，这里的下拉框将全部替换为精美的卡片选择器！</div>
          <button @click="startGame" :disabled="store.isProcessing" class="w-full py-4 bg-emerald-600 hover:bg-emerald-500 font-bold rounded-xl text-lg shadow-lg disabled:opacity-50 transition">
            {{ store.isProcessing ? '🔮 正在创世...' : '🚀 降临新世界' }}
          </button>
        </div>

        <!-- 历史存档网格视图 -->
        <h3 class="text-lg font-bold text-slate-300 mb-4">📂 记忆档案馆 (本地存档)</h3>
        <div v-if="store.availableSaves.length === 0" class="text-slate-500 italic py-8 text-center bg-slate-900/30 rounded-xl border border-dashed border-slate-700">暂无历史记忆，去开启你的第一场冒险吧。</div>
        
        <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          <div v-for="save in store.availableSaves" :key="save" class="bg-aw_panel border border-slate-700 rounded-xl overflow-hidden hover:border-indigo-500 transition group shadow-lg flex flex-col">
            <div class="p-5 border-b border-slate-700/50 flex-1">
              <div class="flex justify-between items-start">
                <h4 class="text-xl font-bold text-indigo-300 line-clamp-1">{{ save }}</h4>
                <span class="px-2 py-1 bg-slate-800 text-xs text-slate-400 rounded">AutoSave</span>
              </div>
              <p class="text-sm text-slate-400 mt-3 line-clamp-2">在这条时间线中，命运仍在等待你的指引...</p>
            </div>
            <div class="flex">
              <button @click="loadGame(save)" :disabled="store.isProcessing" class="flex-1 py-3 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white font-bold transition flex items-center justify-center gap-2">
                ▶️ 延续故事
              </button>
              <button @click="deleteSave(save)" class="px-4 py-3 bg-rose-900/20 hover:bg-rose-600 text-rose-400 hover:text-white border-l border-slate-700 transition" title="删除该存档">
                🗑️
              </button>
            </div>
          </div>
        </div>

      </div>

      <!-- ================= 页面 2：万象工坊 (Workshop) ================= -->
      <div v-else-if="currentMenu === 'workshop'" class="p-8 max-w-7xl mx-auto animate-[fadeIn_0.3s_ease-out]">
        <div class="mb-8 border-b border-slate-700 pb-4">
          <h2 class="text-3xl font-bold text-slate-100">万象工坊</h2>
          <p class="text-slate-400 mt-2">在这里编辑跑团的核心资产，并在大厅或游戏中热插拔。</p>
        </div>

        <!-- 工坊二级导航 -->
        <div class="flex gap-2 mb-8 overflow-x-auto pb-2">
          <button @click="workshopTab = 'character'" :class="workshopTab==='character'?'bg-emerald-600 text-white':'bg-slate-800 text-slate-400 hover:bg-slate-700'" class="px-6 py-2.5 rounded-lg font-bold transition whitespace-nowrap">🎭 角色卡 (Characters)</button>
          <button @click="workshopTab = 'worldbook'" :class="workshopTab==='worldbook'?'bg-emerald-600 text-white':'bg-slate-800 text-slate-400 hover:bg-slate-700'" class="px-6 py-2.5 rounded-lg font-bold transition whitespace-nowrap">🌍 世界书 (Worldbooks)</button>
          <button @click="workshopTab = 'style'" :class="workshopTab==='style'?'bg-emerald-600 text-white':'bg-slate-800 text-slate-400 hover:bg-slate-700'" class="px-6 py-2.5 rounded-lg font-bold transition whitespace-nowrap">📜 文风卡 (Styles)</button>
          <button @click="workshopTab = 'entity'" :class="workshopTab==='entity'?'bg-emerald-600 text-white':'bg-slate-800 text-slate-400 hover:bg-slate-700'" class="px-6 py-2.5 rounded-lg font-bold transition whitespace-nowrap">👾 实体库 (Entities)</button>
        </div>

        <!-- 占位符网格：世界书示例 -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          
          <!-- 新建按钮卡片 -->
          <button class="border-2 border-dashed border-slate-600 rounded-xl flex flex-col items-center justify-center p-8 text-slate-400 hover:text-emerald-400 hover:border-emerald-500 hover:bg-emerald-900/10 transition min-h-[200px]">
            <span class="text-4xl mb-2">+</span>
            <span class="font-bold">铸造新{{ workshopTab === 'entity' ? '实体模板' : '设定' }}</span>
          </button>

          <!-- 模拟渲染现有的数据 -->
          <div v-for="i in 3" :key="i" class="bg-aw_panel border border-slate-700 rounded-xl p-5 hover:border-slate-500 transition relative group flex flex-col justify-between min-h-[200px]">
            <div>
              <h4 class="text-lg font-bold text-slate-200 mb-2">示例设定 {{ i }}</h4>
              <p class="text-xs text-slate-400 line-clamp-3">这是未来将从后端加载的设定详情。你可以直接在这里点击编辑它，所有的修改都会自动保存为 YAML...</p>
            </div>
            <div class="mt-4 flex gap-2">
              <button class="flex-1 bg-slate-800 hover:bg-slate-700 text-xs py-2 rounded text-slate-300 font-bold">✏️ 编辑</button>
            </div>
          </div>
        </div>
      </div>

      <!-- ================= 页面 3：系统终端 (Logs) ================= -->
      <div v-else-if="currentMenu === 'logs'" class="p-8 max-w-5xl mx-auto animate-[fadeIn_0.3s_ease-out] h-full flex flex-col">
        <div class="mb-6">
          <h2 class="text-3xl font-bold text-slate-100 flex items-center gap-3"><span class="text-rose-500">💻</span> 系统统御终端</h2>
          <p class="text-slate-400 mt-2">黑客级日志视图：监控底层 Python 双轨推演与防溃盾的运行状态。</p>
        </div>

        <!-- 终端黑框占位 -->
        <div class="flex-1 bg-[#0c0c0c] border border-slate-700 rounded-xl p-4 font-mono text-xs overflow-y-auto shadow-inner relative">
          <div class="absolute top-4 right-4 text-slate-600 font-bold">LIVE STREAM (UI Placeholder)</div>
          
          <div class="text-emerald-500 mb-2">AliveWorld OS v2.0.0 [Terminal Active]</div>
          <div class="text-slate-400 mb-1">[10:05:22] ℹ️ [FastAPI] Uvicorn running on http://127.0.0.1:8000</div>
          <div class="text-slate-400 mb-1">[10:05:30] ℹ️ [DualTrack] 玩家行动提交："推门而入"</div>
          <div class="text-amber-500 mb-1">[10:05:31] ⚠️ [SalvageEngine] 捕获到不规范的 JSON 换行，防溃盾已启动...</div>
          <div class="text-indigo-400 mb-1">[10:05:35] ✅ [AIEngine] 结算完成，Hp -10, 生成 350 字剧情。</div>
          <div class="text-slate-400 mt-4 animate-pulse">_</div>
        </div>
      </div>

    </main>
  </div>
</template>

<style scoped>
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
</style>