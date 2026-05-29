<!-- aliveworld-ui/src/components/GameUI.vue -->
<script setup>
import { ref, nextTick } from 'vue'
import { store } from '../store.js'

const userInput = ref("")
const lastAction = ref("")
const rightDrawerOpen = ref(false)

const scrollToBottom = async () => {
  await nextTick()
  const container = document.getElementById('chat-container')
  if (container) container.scrollTop = container.scrollHeight
}

const sendPost = async (endpoint, payload = null) => {
  store.isProcessing = true
  try {
    const opts = { method: "POST", headers: { "Content-Type": "application/json" } }
    if (payload) opts.body = JSON.stringify(payload)
    const res = await fetch(`http://127.0.0.1:8000/api/v1/game/${store.sessionId}${endpoint}`, opts)
    if (!res.ok) throw new Error("API 错误")
    return await res.json()
  } catch (e) {
    store.chatLog.push({ role: "system", content: "⚠️ 虚空风暴：连接中断或推演失败" })
    return null
  } finally { store.isProcessing = false }
}

const submitAction = async () => {
  const text = userInput.value.trim()
  if (!text || store.isProcessing) return
  
  store.chatLog.push({ role: "user", content: text })
  lastAction.value = text; userInput.value = ""
  
  const result = await sendPost("/action", { action: text, override_style: store.selectedStyle, override_worldbook: store.selectedWorldbook })
  if (result) {
    // 🚀 修复1：过滤后端返回的 user 消息，防止双重输出
    const newMessages = result.chat_messages.filter(msg => msg.role !== 'user')
    store.chatLog.push(...newMessages)
    store.syncState(result.state)
    scrollToBottom()
  }
}

const undoTurn = async () => {
  const result = await sendPost("/undo")
  if (result) { store.chatLog = result.chat_messages; store.syncState(result.state); scrollToBottom() }
}

const retryTurn = async () => {
  if (!lastAction.value) return
  const result = await sendPost("/retry", { action: lastAction.value, override_style: store.selectedStyle, override_worldbook: store.selectedWorldbook })
  if (result) { store.chatLog = result.full_chat; store.syncState(result.state); scrollToBottom() }
}
</script>

<template>
  <div class="flex-1 flex relative overflow-hidden bg-aw_bg text-slate-200 h-full w-full">
    <!-- 左侧雷达 -->
    <aside class="w-72 bg-aw_panel border-r border-slate-700 flex flex-col z-20 shadow-xl">
      <div class="p-4 border-b border-slate-700 bg-slate-900/50 flex justify-between items-center">
        <div><h1 class="text-xl font-bold text-emerald-400">🐉 AliveWorld</h1></div>
        <button @click="store.isInLobby=true" class="text-xs bg-slate-700 hover:bg-slate-600 px-2 py-1 rounded transition">🚪 返回</button>
      </div>
      <div class="p-4 flex-1 overflow-y-auto space-y-6">
        <div>
          <div class="flex justify-between text-sm mb-1"><span class="text-red-400 font-bold">❤️ 生命值</span><span class="font-mono text-slate-300">{{ store.playerState.hp }} / {{ store.playerState.maxHp }}</span></div>
          <div class="w-full bg-slate-800 rounded-full h-2"><div class="bg-gradient-to-r from-red-600 to-red-400 h-2 rounded-full transition-all" :style="{ width: (store.playerState.hp / store.playerState.maxHp * 100) + '%' }"></div></div>
        </div>
        <div v-if="Object.keys(store.dynamicBars).length > 0">
          <div v-for="(bar, name) in store.dynamicBars" :key="name" class="mb-3">
            <div class="flex justify-between text-xs mb-1"><span class="text-indigo-400 font-bold">💠 {{ name }}</span><span class="font-mono">{{ bar.current }}/{{ bar.max }}</span></div>
            <div class="w-full bg-slate-800 rounded-full h-1.5"><div class="bg-gradient-to-r from-indigo-600 to-indigo-400 h-1.5 rounded-full" :style="{ width: Math.max(0, Math.min(100, (bar.current / bar.max * 100))) + '%' }"></div></div>
          </div>
        </div>
        <div v-if="Object.keys(store.properties).length > 0">
          <h3 class="text-xs text-slate-400 mb-2 font-bold uppercase tracking-wider">🏷️ 状态与时间</h3>
          <div class="flex flex-col gap-1.5">
            <!-- 🚀 修复2：动态过滤包含"时间"的属性 -->
            <div v-for="(val, key) in store.properties" :key="key" 
                 v-show="store.uiSettings?.showTime || !key.includes('时间')"
                 class="bg-slate-800/80 p-2 rounded text-xs flex justify-between shadow-sm">
              <span class="text-slate-400">{{ key }}</span><span class="text-emerald-200">{{ val }}</span>
            </div>
          </div>
        </div>
        <div v-if="Object.keys(store.npcs).length > 0">
          <h3 class="text-xs text-slate-400 mb-2 font-bold uppercase tracking-wider">👾 实体观测</h3>
          <div class="flex flex-col gap-2">
            <div v-for="(statusStr, name) in store.npcs" :key="name" class="bg-slate-800/60 p-2 rounded border border-indigo-900/50 shadow-sm relative">
              <div class="absolute left-0 top-0 bottom-0 w-1 bg-indigo-500"></div><span class="text-indigo-300 font-bold text-sm ml-2">{{ name }}</span>
              <div class="flex flex-wrap gap-1 mt-1 ml-2"><span v-for="(tag, idx) in String(statusStr).split(',')" :key="idx" class="px-1.5 py-0.5 bg-indigo-950 border border-indigo-700/50 rounded-sm text-[10px] text-indigo-200">{{ tag.trim() }}</span></div>
            </div>
          </div>
        </div>
      </div>
    </aside>

    <!-- 中间主推演流 -->
    <main class="flex-1 flex flex-col relative z-0">
      <header class="h-14 bg-aw_panel/95 backdrop-blur border-b border-slate-700 flex justify-between items-center px-4 absolute top-0 w-full z-10 shadow-md">
        <div class="text-sm text-slate-300">当前界域: <span class="text-indigo-300 font-bold">{{ store.selectedWorldbook }}</span></div>
        <button @click="rightDrawerOpen = !rightDrawerOpen" class="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 rounded-md font-bold transition shadow-lg shadow-indigo-900/50">⚙️ 统御控制台</button>
      </header>

      <div class="flex-1 overflow-y-auto p-4 space-y-6 pt-20 pb-36 scroll-smooth" id="chat-container">
        <div v-for="(msg, idx) in store.chatLog" :key="idx" class="flex flex-col" :class="msg.role === 'user' ? 'items-end' : 'items-start'">
          <div v-if="msg.role === 'reactions'" class="text-xs text-amber-500 mb-1 px-3 py-1.5 bg-amber-500/10 border border-amber-500/30 rounded-md font-mono">🎲 {{ store.formatContent(msg.content) }}</div>
          <div v-else-if="msg.role === 'system'" class="text-xs text-rose-400 mb-1 px-3 py-1.5 bg-rose-500/10 border border-rose-500/30 rounded-md italic">{{ store.formatContent(msg.content) }}</div>
          <div v-else class="max-w-[80%] rounded-xl p-4 whitespace-pre-wrap leading-relaxed shadow-lg" :class="msg.role === 'user' ? 'bg-indigo-600 text-white rounded-br-none' : 'bg-slate-800 text-slate-200 border border-slate-600 rounded-bl-none'" v-text="store.formatContent(msg.content)"></div>
        </div>
        <div v-if="store.isProcessing" class="text-emerald-400 text-sm font-bold italic animate-pulse">🧠 引擎双轨推演中...</div>
      </div>

      <div class="absolute bottom-0 w-full p-4 bg-gradient-to-t from-aw_bg via-aw_bg to-transparent z-10">
        <div class="max-w-4xl mx-auto flex flex-col gap-2">
          <div class="flex justify-end gap-2 px-1" v-if="store.chatLog.length > 1 && !store.isProcessing">
            <button @click="undoTurn" class="px-3 py-1.5 text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-300 rounded shadow border border-slate-600 transition">⏪ 撤回</button>
            <button @click="retryTurn" class="px-3 py-1.5 text-xs font-bold bg-indigo-900/80 hover:bg-indigo-700 text-indigo-200 rounded shadow border border-indigo-600 transition">🔄 重试</button>
          </div>
          <div class="relative flex gap-3 drop-shadow-2xl">
            <input v-model="userInput" @keyup.enter="submitAction" :disabled="store.isProcessing" class="flex-1 bg-slate-800/95 border border-slate-600 rounded-lg px-4 py-3 outline-none focus:border-indigo-500 text-slate-200 placeholder-slate-500" placeholder="轮到你了..." />
            <button @click="submitAction" :disabled="store.isProcessing" class="px-8 py-3 bg-emerald-600 hover:bg-emerald-500 rounded-lg font-bold disabled:opacity-50 transition shadow-lg shadow-emerald-900/50">执行</button>
          </div>
        </div>
      </div>
    </main>

    <!-- 右侧热插拔控制台 -->
    <div v-if="rightDrawerOpen" @click="rightDrawerOpen = false" class="absolute inset-0 bg-black/40 z-30 transition-opacity"></div>
    <aside v-if="rightDrawerOpen" class="w-80 bg-aw_panel border-l border-slate-600 shadow-2xl absolute right-0 top-0 h-full z-40 flex flex-col slide-in">
      <div class="p-4 flex justify-between items-center border-b border-slate-700 bg-slate-900/50"><h2 class="font-bold text-indigo-400">⚙️ 统御控制台</h2><button @click="rightDrawerOpen = false" class="text-slate-400 hover:text-white text-xl">×</button></div>
      <div class="p-5 flex-1 space-y-6">
        <div><label class="text-xs font-bold text-slate-400 mb-2 block">🎭 动态文风热插拔</label><select v-model="store.selectedStyle" class="w-full bg-slate-800 border border-slate-600 rounded p-2.5 outline-none focus:border-indigo-500 text-sm text-slate-200"><option>默认 (无)</option><option v-for="s in store.availableStyles" :key="s" :value="s">{{ s }}</option></select></div>
        <div><label class="text-xs font-bold text-slate-400 mb-2 block">🌌 注入新世界书</label><select v-model="store.selectedWorldbook" class="w-full bg-slate-800 border border-slate-600 rounded p-2.5 outline-none focus:border-indigo-500 text-sm text-slate-200"><option>无界域 (暂不加载)</option><option v-for="w in store.availableWorldbooks" :key="w" :value="w">{{ w }}</option></select></div>
        
        <!-- 🚀 修复3：时间开关设置区 -->
        <div class="mt-6 border-t border-slate-700 pt-6">
          <h3 class="text-xs font-bold text-slate-400 mb-3 uppercase tracking-wider">👁️ 界面呈现设置</h3>
          <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer hover:text-white transition">
            <!-- 确保 store.js 里添加了 uiSettings: { showTime: false } -->
            <input type="checkbox" v-model="store.uiSettings.showTime" class="w-4 h-4 rounded border-slate-600 bg-slate-800 text-indigo-500 focus:ring-indigo-500">
            <span>显示“当前时间”状态</span>
          </label>
        </div>
      </div>
    </aside>
  </div>
</template>