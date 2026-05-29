<!-- src/components/RightDrawer.vue -->
<script setup>
import { store } from '../store.js'

const loadGame = async (saveName) => {
  store.isProcessing = true
  try {
    const response = await fetch("http://127.0.0.1:8000/api/v1/game/load", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ save_name: saveName }) })
    if (response.ok) {
      const data = await response.json(); store.sessionId = data.session_id; store.chatLog = data.chat_messages || []; store.syncState(data.state); store.rightTab = 'local_edit'
    } else alert("存档读取失败")
  } catch (err) {} finally { store.isProcessing = false }
}
</script>

<template>
  <aside :class="store.rightDrawerOpen ? 'w-[350px]' : 'w-0'" class="bg-aw_panel border-l border-slate-700 flex flex-col transition-all duration-300 z-30 shadow-2xl overflow-hidden relative shrink-0">
    <div class="flex text-xs font-bold border-b border-slate-700 bg-slate-900/80 min-w-[22rem]">
      <button @click="store.rightTab = 'archive'" :class="store.rightTab==='archive'?'text-indigo-400 border-b-2 border-indigo-400 bg-slate-800':'text-slate-500 hover:text-slate-300'" class="flex-1 py-3 transition">📂 档案</button>
      <button @click="store.rightTab = 'local_edit'" :class="store.rightTab==='local_edit'?'text-emerald-400 border-b-2 border-emerald-400 bg-slate-800':'text-slate-500 hover:text-slate-300'" class="flex-1 py-3 transition">⚙️ 局内</button>
      <button @click="store.rightTab = 'ai_forge'" :class="store.rightTab==='ai_forge'?'text-purple-400 border-b-2 border-purple-400 bg-slate-800':'text-slate-500 hover:text-slate-300'" class="flex-1 py-3 transition">🧠 偏好</button>
      <button @click="store.rightTab = 'gallery'" :class="store.rightTab==='gallery'?'text-amber-400 border-b-2 border-amber-400 bg-slate-800':'text-slate-500 hover:text-slate-300'" class="flex-1 py-3 transition">🖼️ 画廊</button>
    </div>

    <div class="flex-1 overflow-y-auto min-w-[22rem] custom-scrollbar">
      
      <!-- 档案 -->
      <div v-if="store.rightTab === 'archive'" class="p-3">
        <div class="flex justify-between items-center text-xs text-slate-500 mb-3 px-1"><span>时间线列表</span><button class="hover:text-white">时间排序 ▼</button></div>
        <div class="space-y-2">
          <div v-for="save in store.availableSaves" :key="save.name" class="flex items-center gap-3 p-2 bg-slate-800/40 border border-slate-700 rounded-lg hover:border-indigo-500 cursor-pointer group transition" @click="loadGame(save.name)">
            <div class="w-10 h-10 rounded bg-slate-900 flex items-center justify-center text-xl shadow-inner">{{ save.avatar }}</div>
            <div class="flex-1 min-w-0"><h4 class="text-sm font-bold text-slate-200 truncate group-hover:text-indigo-300">{{ save.name }}</h4><div class="text-[10px] text-slate-500 mt-0.5">上次存档: {{ save.date }}</div></div>
          </div>
        </div>
      </div>

      <!-- 局内设定 -->
      <div v-if="store.rightTab === 'local_edit'" class="p-5 space-y-6">
        <div v-if="!store.sessionId" class="text-center text-slate-500 text-sm mt-10">未连接故事线</div>
        <template v-else>
          <div>
            <h3 class="text-xs font-bold text-slate-400 mb-2">🧭 剧情导向 (Plot Compass)</h3>
            <textarea v-model="store.localSettings.plotCompass" class="w-full h-24 bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs text-slate-300 outline-none focus:border-indigo-500 resize-none shadow-inner" placeholder="输入你想给 AI 的主干指导，例如：放慢节奏，触发遭遇战..."></textarea>
          </div>
          <div class="border-t border-slate-700 pt-4">
             <h3 class="text-xs font-bold text-slate-400 mb-2">👁️ 界面视觉覆盖</h3>
             <select v-model="store.localSettings.showTime" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-xs text-slate-300 outline-none">
               <option :value="null">跟随全局设置</option><option :value="true">强制开启状态字典</option><option :value="false">强制隐藏状态字典</option>
             </select>
          </div>
          <div class="border-t border-slate-700 pt-4">
            <div class="flex justify-between items-center mb-2"><h3 class="text-xs font-bold text-slate-400">📜 局内独立世界书</h3><button class="text-[10px] bg-slate-800 hover:bg-indigo-600 px-2 py-1 rounded transition text-slate-300">保存至全局</button></div>
            <textarea class="w-full h-32 bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs text-slate-500 outline-none cursor-not-allowed shadow-inner" disabled placeholder="(开发中) 当前存档独占的设定..."></textarea>
          </div>
        </template>
      </div>

      <!-- 🚀 AI 偏好 (新增逼真卡片) -->
      <div v-if="store.rightTab === 'ai_forge'" class="p-5 space-y-6">
        <div class="bg-gradient-to-br from-purple-900/30 to-slate-900 border border-purple-700/50 p-4 rounded-xl shadow-lg relative overflow-hidden">
          <div class="absolute -right-4 -top-4 text-6xl opacity-10">🧠</div>
          <h3 class="font-bold text-purple-400 mb-2 text-sm">潜意识档案 (Player Profile)</h3>
          <p class="text-[10px] text-slate-400 mb-4 leading-relaxed">AI 观察器已开启。根据您前 20 回合的抉择，引擎为您偷偷生成的专属偏好设定卡。</p>
          <div class="bg-black/40 rounded p-3 text-xs text-purple-200 font-mono leading-relaxed border border-purple-900">
            [性格倾向]：谨慎、喜欢收集情报<br>
            [战斗偏好]：倾向于潜行与暗杀<br>
            [叙事要求]：喜欢详细的环境描写，不排斥血腥表现<br>
            <span class="text-purple-500 italic mt-2 block">/* 此卡片将在后续生成中作为隐藏提示词注入 */</span>
          </div>
          <button class="w-full mt-4 py-2 bg-purple-600/30 hover:bg-purple-600 text-purple-300 hover:text-white border border-purple-500/50 rounded transition text-xs font-bold">手动编辑偏好</button>
        </div>
      </div>

      <!-- 🚀 画廊 CG -->
      <div v-if="store.rightTab === 'gallery'" class="p-4">
        <div class="flex justify-between items-center mb-4"><h3 class="text-sm font-bold text-slate-300">回忆画廊</h3><span class="text-xs text-amber-500">2 解锁</span></div>
        <div class="grid grid-cols-2 gap-3">
          <div v-for="(img, idx) in store.unlockedCGs" :key="idx" class="aspect-square bg-slate-800 rounded-lg border border-slate-700 overflow-hidden group cursor-pointer relative">
            <img :src="img" class="w-full h-full object-cover opacity-70 group-hover:opacity-100 group-hover:scale-110 transition duration-500">
            <div class="absolute inset-0 border-2 border-amber-500/0 group-hover:border-amber-500/50 rounded-lg transition"></div>
          </div>
          <div class="aspect-square bg-slate-900 rounded-lg border border-dashed border-slate-700 flex items-center justify-center text-slate-600 text-2xl">🔒</div>
        </div>
      </div>

    </div>
  </aside>
</template>