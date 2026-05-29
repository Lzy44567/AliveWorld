<!-- aliveworld-ui/src/App.vue -->
<script setup>
import { ref } from 'vue'
import { store } from './store.js'

const userInput = ref("")
const newSaveName = ref("")
const searchKeyword = ref("") 
const searchSaveKeyword = ref("") // 存档专属搜索

const submitAction = (text = null) => {
  const finalAction = text || userInput.value.trim()
  if (!finalAction) return
  store.chatLog.push({ role: "user", content: finalAction })
  userInput.value = ""
  store.isProcessing = true
  setTimeout(() => {
    store.chatLog.push({ role: "reactions", content: [{id:1, weight:80, description:"门被踹开，警报大作"}] })
    store.chatLog.push({ role: "system", content: "命运裁定：门被踹开，警报大作" })
    store.chatLog.push({ role: "ai", content: "你猛地一脚踹开大门！\n\n机械守卫锁定了你。\n\n「发现入侵者，授权击毙。」" })
    store.playerState.hp -= 5
    store.isProcessing = false
  }, 1000)
}

const openInsertCharModal = (charName) => {
  store.insertCharData.name = charName
  store.insertCharData.entrance = ""
  store.modals.insertChar = true
}
</script>

<template>
  <div class="h-screen w-screen flex flex-col bg-aw_bg text-slate-200 overflow-hidden font-sans selection:bg-indigo-500/30">
    
    <!-- ================= 顶部导航 (Top Bar) ================= -->
    <header class="h-12 bg-slate-900 border-b border-slate-700 flex justify-between items-center px-4 z-50 shadow-md shrink-0">
      <div class="flex items-center gap-4">
        <button @click="store.leftDrawerOpen = !store.leftDrawerOpen" class="text-slate-400 hover:text-emerald-400 transition" title="局内雷达"><span class="text-xl">☷</span></button>
        <span class="font-black text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-indigo-400 text-lg tracking-widest">ALIVEWORLD</span>
      </div>
      <div class="flex items-center gap-3">
        <button @click="store.modals.gallery = true" class="text-slate-400 hover:text-amber-400 flex items-center gap-1 text-sm font-bold"><span class="text-lg">🖼️</span> 画廊</button>
        <button @click="store.modals.terminal = true" class="text-slate-400 hover:text-rose-400 flex items-center gap-1 text-sm font-bold"><span class="text-lg">💻</span> 日志</button>
        <button @click="store.modals.settings = true" class="text-slate-400 hover:text-indigo-400 flex items-center gap-1 text-sm font-bold"><span class="text-lg">⚙️</span> 设置</button>
        <div class="w-px h-6 bg-slate-700 mx-2"></div>
        <button @click="store.rightDrawerOpen = !store.rightDrawerOpen" class="text-slate-400 hover:text-emerald-400 transition" title="万象资产"><span class="text-xl">☰</span></button>
      </div>
    </header>

    <div class="flex-1 flex overflow-hidden relative">
      
      <!-- ================= 左侧：局内战术雷达 ================= -->
      <aside :class="store.leftDrawerOpen ? 'w-[320px]' : 'w-0'" class="bg-aw_panel border-r border-slate-700 flex flex-col transition-all duration-300 z-20 shadow-xl overflow-hidden relative shrink-0">
        <div class="flex-1 overflow-y-auto p-4 space-y-6 min-w-[320px] custom-scrollbar">
          <div v-if="!store.sessionId" class="h-full flex items-center justify-center text-slate-500 text-sm italic">等待唤醒故事线...</div>
          <template v-else>
            <!-- 玩家状态 -->
            <div>
              <h3 class="text-xs text-slate-500 mb-2 font-bold uppercase">👤 玩家 (Player)</h3>
              <div class="bg-slate-800/80 p-3 rounded-lg border border-slate-700 shadow-inner">
                 <div class="flex justify-between text-xs mb-1 text-slate-300 font-bold"><span>HP</span><span class="font-mono text-emerald-400">{{ store.playerState.hp }}/{{ store.playerState.maxHp }}</span></div>
                 <div class="w-full bg-slate-950 rounded-full h-1.5 mb-3"><div class="bg-gradient-to-r from-red-600 to-red-400 h-1.5 rounded-full transition-all" :style="{ width: (store.playerState.hp / store.playerState.maxHp * 100) + '%' }"></div></div>
                 <div v-for="(bar, name) in store.dynamicBars" :key="name" class="mb-2">
                   <div class="flex justify-between text-[10px] mb-1 text-slate-400"><span>{{ name }}</span><span class="font-mono">{{ bar.current }}/{{ bar.max }}</span></div>
                   <div class="w-full bg-slate-950 rounded-full h-1"><div class="bg-indigo-500 h-1 rounded-full" :style="{ width: Math.max(0, Math.min(100, (bar.current / bar.max * 100))) + '%' }"></div></div>
                 </div>
              </div>
            </div>

            <!-- 编队系统 -->
            <div v-if="store.companions && store.companions.length > 0">
              <h3 class="text-xs text-slate-500 mb-2 font-bold uppercase">👥 同行者 (Party)</h3>
              <div class="flex flex-col gap-2">
                <div v-for="(comp, idx) in store.companions" :key="idx" class="bg-slate-800/60 p-2.5 rounded-lg border border-slate-700 flex gap-3 hover:border-indigo-500 cursor-pointer transition shadow-sm">
                  <div class="w-10 h-10 rounded bg-slate-700 flex items-center justify-center text-xl shadow-inner shrink-0">{{ comp.avatar }}</div>
                  <div class="flex-1 min-w-0 flex flex-col justify-center">
                    <div class="flex justify-between items-center mb-1"><span class="text-xs font-bold text-slate-200">{{ comp.name }}</span><div class="w-12 bg-slate-900 rounded-full h-1"><div class="bg-emerald-500 h-1 rounded-full" :style="{ width: (comp.hp / comp.maxHp * 100) + '%' }"></div></div></div>
                    <div class="text-[10px] text-slate-400 leading-snug whitespace-pre-wrap">{{ comp.status }}</div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 环境与 NPC -->
            <div v-if="Object.keys(store.properties).length > 0 || Object.keys(store.npcs).length > 0">
              <h3 class="text-xs text-slate-500 mb-2 font-bold uppercase">📡 场景与实体感知</h3>
              <div class="space-y-2">
                <div v-for="(val, key) in store.properties" :key="key" v-show="store.shouldShowTime || !key.includes('时间')" class="bg-slate-800/80 px-2 py-1.5 rounded text-[11px] flex justify-between shadow-sm border border-slate-700/50"><span class="text-slate-400">{{ key }}</span><span class="text-emerald-300 font-bold">{{ val }}</span></div>
                <div v-for="(statusStr, name) in store.npcs" :key="name" class="bg-slate-800/60 p-2 rounded border border-rose-900/50 shadow-sm relative"><div class="absolute left-0 top-0 bottom-0 w-1 bg-rose-500"></div><span class="text-rose-300 font-bold text-xs ml-2">{{ name }}</span><div class="flex flex-wrap gap-1 mt-1 ml-2"><span v-for="(tag, idx) in String(statusStr).split(',')" :key="idx" class="px-1.5 py-0.5 bg-rose-950 border border-rose-700/50 rounded text-[9px] text-rose-200">{{ tag.trim() }}</span></div></div>
              </div>
            </div>

            <!-- 场景地图 -->
            <div v-if="store.localSettings.showMap" class="border-t border-slate-700 pt-4 pb-6">
              <h3 class="text-xs text-slate-500 mb-2 font-bold uppercase flex justify-between items-center"><span>🗺️ 区域地图</span><button class="text-indigo-400 hover:text-white text-[10px]">全屏</button></h3>
              <div class="h-28 bg-slate-900 rounded-lg border border-slate-700 overflow-hidden relative group mb-3 shadow-lg">
                <img :src="store.currentScene.img" class="w-full h-full object-cover opacity-60 group-hover:opacity-100 transition duration-500">
                <div class="absolute bottom-0 w-full bg-gradient-to-t from-black via-black/80 to-transparent p-2 text-xs font-bold text-white">{{ store.currentScene.name }}</div>
              </div>
            </div>
          </template>
        </div>
      </aside>

      <!-- ================= 中间：沉浸推演流 ================= -->
      <main class="flex-1 flex flex-col relative z-0 bg-aw_bg overflow-hidden">
        <div class="absolute inset-0 z-0 opacity-15 pointer-events-none"><img :src="store.currentScene.img" class="w-full h-full object-cover blur-sm"></div>
        <div class="absolute bottom-0 right-12 z-0 pointer-events-none transition-all duration-700 ease-out" :class="store.isSpeakerActive && store.sessionId ? 'opacity-90 translate-y-0' : 'opacity-0 translate-y-10'">
          <div class="w-[450px] h-[650px] relative"><img :src="store.currentSpeakerSprite" class="w-full h-full object-cover rounded-t-full shadow-2xl drop-shadow-[0_0_15px_rgba(0,0,0,0.8)]" style="mask-image: linear-gradient(to top, transparent 10%, black 50%); -webkit-mask-image: linear-gradient(to top, transparent 5%, black 40%);"></div>
        </div>

        <div class="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 pb-48 z-10 custom-scrollbar" id="chat-container">
          <div v-if="!store.sessionId" class="h-full flex items-center justify-center flex-col text-center">
             <h2 class="text-4xl font-bold text-slate-300 mb-4 tracking-widest">A L I V E W O R L D</h2><p class="text-slate-500">世界的齿轮尚未转动</p>
          </div>
          <template v-else>
            <div v-for="(msg, idx) in store.chatLog" :key="idx" class="flex flex-col" :class="msg.role === 'user' ? 'items-end' : 'items-start'">
              <div v-if="msg.role === 'reactions' && store.settings.showFutures" class="w-full max-w-[85%] bg-amber-950/60 border border-amber-700/50 rounded-xl overflow-hidden backdrop-blur-md shadow-lg mb-2">
                <details class="group"><summary class="cursor-pointer px-4 py-2.5 text-xs text-amber-400 font-bold flex justify-between items-center hover:bg-amber-900/50 transition select-none"><span>🎲 观测到 {{ msg.content.length }} 种时间线</span><span class="group-open:rotate-180 transition">▼</span></summary>
                <div class="px-4 py-3 border-t border-amber-900/50 space-y-2"><div v-for="r in msg.content" :key="r.id" class="flex items-center gap-3 text-xs text-amber-200 bg-black/40 p-2 rounded hover:bg-black/60 transition"><div class="w-10 text-center font-mono font-bold bg-amber-600/40 rounded px-1">{{ r.weight }}%</div><div class="flex-1">{{ r.description }}</div></div></div></details>
              </div>
              <div v-else-if="msg.role === 'system' && store.settings.showDice" class="text-xs text-rose-400 mb-2 px-4 py-2 bg-rose-950/80 border border-rose-700/50 rounded-lg backdrop-blur-md italic shadow-md max-w-[85%] flex justify-between items-center group">
                <span>{{ msg.content }}</span><button v-if="store.settings.allowReroll" class="hidden group-hover:block px-3 py-1 bg-rose-800 hover:bg-rose-600 text-white rounded text-[10px] font-bold transition ml-4 shadow">🔄 重掷</button>
              </div>
              <div v-else-if="msg.role === 'user' || msg.role === 'ai'" class="max-w-[85%] rounded-2xl p-5 whitespace-pre-wrap leading-relaxed shadow-2xl text-[15px] backdrop-blur-md" :class="msg.role === 'user' ? 'bg-indigo-600/95 text-white rounded-br-sm' : 'bg-slate-900/90 border border-slate-600 text-slate-200 rounded-bl-sm'">{{ store.formatContent(msg.content) }}</div>
            </div>
            <div v-if="store.isProcessing" class="text-emerald-400 text-sm font-bold italic animate-pulse">🧠 引擎推演中...</div>
          </template>
        </div>

        <div class="absolute bottom-0 w-full p-6 bg-gradient-to-t from-aw_bg via-aw_bg/95 to-transparent z-20">
          <div class="max-w-4xl mx-auto flex flex-col gap-2">
            <div class="flex gap-2 px-1 mb-1 overflow-x-auto custom-scrollbar" v-if="store.settings.aiSuggestions && !store.isProcessing && store.sessionId">
              <button v-for="(sug, idx) in store.aiSuggestions" :key="idx" @click="submitAction(sug)" class="px-4 py-2 text-xs font-bold bg-slate-800/80 hover:bg-emerald-600/80 text-slate-300 hover:text-white border border-slate-600 hover:border-emerald-500 rounded-full transition whitespace-nowrap backdrop-blur shadow-lg">💡 {{ sug }}</button>
            </div>
            <div class="relative flex gap-3 drop-shadow-2xl">
              <input v-model="userInput" @keyup.enter="submitAction()" :disabled="store.isProcessing || !store.sessionId" class="flex-1 bg-slate-900/90 border border-slate-600 rounded-xl px-5 py-4 outline-none focus:border-indigo-500 text-slate-100 placeholder-slate-500 shadow-inner text-base backdrop-blur" placeholder="描述你的行动..." />
              <div class="flex flex-col gap-1 justify-center">
                 <button class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded text-[10px] border border-slate-700 transition" title="撤回">⏪</button><button class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded text-[10px] border border-slate-700 transition" title="重试">🔄</button>
              </div>
              <button @click="submitAction()" :disabled="store.isProcessing || !store.sessionId" class="px-8 py-4 bg-emerald-600 hover:bg-emerald-500 rounded-xl font-bold disabled:opacity-50 transition shadow-lg text-lg">发送</button>
            </div>
          </div>
        </div>
      </main>

      <!-- ================= 右侧：万象资产控制台 ================= -->
      <aside :class="store.rightDrawerOpen ? 'w-[400px]' : 'w-0'" class="bg-aw_panel border-l border-slate-700 flex flex-col transition-all duration-300 z-30 shadow-2xl overflow-hidden relative shrink-0">
        
        <!-- 顶级 Tab -->
        <div class="flex text-lg border-b border-slate-700 bg-slate-900 min-w-[400px] shrink-0">
          <button @click="store.rightTab = 'saves'" :class="store.rightTab==='saves'?'text-emerald-400 border-b-2 border-emerald-400 bg-slate-800':'text-slate-500 hover:bg-slate-800/50'" class="flex-1 py-3 transition" title="故事线/存档">📂</button>
          <button @click="store.rightTab = 'character'" :class="store.rightTab==='character'?'text-indigo-400 border-b-2 border-indigo-400 bg-slate-800':'text-slate-500 hover:bg-slate-800/50'" class="flex-1 py-3 transition" title="角色卡库">🎭</button>
          <button @click="store.rightTab = 'world'" :class="store.rightTab==='world'?'text-amber-400 border-b-2 border-amber-400 bg-slate-800':'text-slate-500 hover:bg-slate-800/50'" class="flex-1 py-3 transition" title="世界法则">🌍</button>
          <button @click="store.rightTab = 'style'" :class="store.rightTab==='style'?'text-rose-400 border-b-2 border-rose-400 bg-slate-800':'text-slate-500 hover:bg-slate-800/50'" class="flex-1 py-3 transition" title="文风卡">📜</button>
          <button @click="store.rightTab = 'entity'" :class="store.rightTab==='entity'?'text-purple-400 border-b-2 border-purple-400 bg-slate-800':'text-slate-500 hover:bg-slate-800/50'" class="flex-1 py-3 transition" title="暗流实体">👾</button>
          <button @click="store.rightTab = 'local_edit'" :class="store.rightTab==='local_edit'?'text-cyan-400 border-b-2 border-cyan-400 bg-slate-800':'text-slate-500 hover:bg-slate-800/50'" class="flex-1 py-3 transition" title="局内独立设定">⚙️</button>
        </div>

        <div class="flex-1 overflow-y-auto bg-slate-900/30 min-w-[400px] custom-scrollbar p-4 relative">
          <h2 class="text-sm font-bold text-slate-200 mb-3 tracking-wider">{{ store.tabTitles[store.rightTab] || "数据面板" }}</h2>

          <!-- 模块 1：四大资产库 (Char/World/Style/Entity) -->
          <div v-if="['character', 'world', 'style', 'entity'].includes(store.rightTab)" class="flex flex-col h-full animate-[fadeIn_0.2s]">
            <!-- 局内/全局 切换 -->
            <div class="flex bg-slate-900 rounded-lg p-1 border border-slate-700 shadow-inner mb-4 shrink-0">
              <button @click="store.assetScope = 'local'" :class="store.assetScope==='local'?'bg-slate-700 text-white shadow':'text-slate-400 hover:text-slate-200'" class="flex-1 py-1.5 rounded text-xs font-bold transition">🛡️ 本局专属</button>
              <button @click="store.assetScope = 'global'" :class="store.assetScope==='global'?'bg-slate-700 text-white shadow':'text-slate-400 hover:text-slate-200'" class="flex-1 py-1.5 rounded text-xs font-bold transition">🌐 全局图鉴</button>
            </div>
            
            <!-- 搜索与过滤工具栏 -->
            <div class="flex gap-2 mb-4 shrink-0">
              <div class="flex-1 relative">
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-xs">🔍</span>
                <input v-model="searchKeyword" class="w-full bg-slate-800 border border-slate-600 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 outline-none focus:border-indigo-500" placeholder="搜索名称或标签..." />
              </div>
              <button class="w-8 h-8 bg-slate-800 border border-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-amber-400 transition" title="收藏">⭐</button>
              <button class="w-8 h-8 bg-slate-800 border border-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-indigo-400 transition" title="标签过滤">🏷️</button>
              <button class="px-2 h-8 bg-emerald-600/20 text-emerald-400 border border-emerald-700/50 rounded-lg hover:bg-emerald-600 hover:text-white transition text-xs font-bold whitespace-nowrap">+ 新建</button>
            </div>
            
            <!-- 卡片列表 -->
            <div class="space-y-3">
               <div v-for="item in (store.rightTab === 'world' ? store.worlds[store.assetScope] : store.rightTab === 'character' ? store.characters[store.assetScope] : store.rightTab === 'style' ? store.styles[store.assetScope] : store.entities[store.assetScope])" :key="item.name" 
                    class="bg-aw_panel border border-slate-700 p-3 rounded-xl hover:border-indigo-500 transition group shadow flex flex-col gap-2 relative overflow-hidden">
                 <div v-if="item.status" class="absolute right-0 top-0 bg-rose-900/80 text-rose-200 text-[9px] px-2 py-0.5 rounded-bl-lg">{{ item.status }}</div>
                 <h4 class="text-sm font-bold text-slate-200 group-hover:text-indigo-400 transition">{{ item.name }}</h4>
                 <div class="flex flex-wrap gap-1"><span v-for="t in item.tags" :key="t" class="bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded text-[9px] border border-slate-700">{{ t }}</span></div>
                 <p class="text-xs text-slate-500 line-clamp-2 mt-1 leading-relaxed">{{ item.desc }}</p>
                 <div class="mt-2 flex gap-2 border-t border-slate-800 pt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                   <button class="flex-1 bg-slate-800 hover:bg-slate-700 text-[10px] py-1.5 rounded font-bold text-slate-300">✏️ 编辑</button>
                   <button v-if="store.assetScope==='global' && store.rightTab==='character'" @click="openInsertCharModal(item.name)" class="flex-1 bg-indigo-900/50 hover:bg-indigo-600 text-[10px] py-1.5 rounded font-bold text-indigo-300 hover:text-white border border-indigo-700/50">⬇️ 安排登场</button>
                   <button v-else-if="store.assetScope==='global'" class="flex-1 bg-indigo-900/50 hover:bg-indigo-600 text-[10px] py-1.5 rounded font-bold text-indigo-300 hover:text-white border border-indigo-700/50">⬇️ 载入局内</button>
                   <button v-if="store.assetScope==='local'" class="flex-1 bg-emerald-900/50 hover:bg-emerald-600 text-[10px] py-1.5 rounded font-bold text-emerald-300 hover:text-white border border-emerald-700/50">⬆️ 提取到全局</button>
                 </div>
               </div>
            </div>
          </div>

          <!-- ================= 模块 2：故事线存档 (Saves) ================= -->
          <div v-if="store.rightTab === 'saves'" class="flex flex-col h-full animate-[fadeIn_0.2s]">
             <!-- 🚀 修复：统一布局的工具栏 -->
             <div class="flex gap-2 mb-4 shrink-0">
              <div class="flex-1 relative">
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-xs">🔍</span>
                <input v-model="searchSaveKeyword" class="w-full bg-slate-800 border border-slate-600 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 outline-none focus:border-indigo-500" placeholder="搜索记忆切片..." />
              </div>
              <button class="w-8 h-8 bg-slate-800 border border-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-amber-400 transition" title="收藏">⭐</button>
              <button class="px-3 h-8 bg-emerald-600/20 text-emerald-400 border border-emerald-700/50 rounded-lg hover:bg-emerald-600 hover:text-white transition text-xs font-bold whitespace-nowrap" @click="store.modals.newGame = true">+ 新局</button>
            </div>
             
             <div class="flex justify-between items-center text-xs text-slate-500 mb-2 px-1"><span>记忆档案</span><span>共 {{store.saves.length}} 份</span></div>
             <div class="space-y-3">
               <div v-for="save in store.saves" :key="save.id" class="bg-aw_panel border border-slate-700 rounded-xl p-3 hover:border-indigo-500 transition cursor-pointer group shadow">
                 <div class="flex justify-between items-start mb-2"><h4 class="text-sm font-bold text-slate-200 group-hover:text-indigo-400">{{ save.name }}</h4><span class="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded border border-slate-700">{{ save.type }}</span></div>
                 <p class="text-xs text-slate-500 mb-3 line-clamp-1">{{ save.desc }}</p>
                 <div class="flex gap-2">
                   <button class="flex-1 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white text-[10px] py-1.5 rounded font-bold transition">▶ 唤醒</button>
                   <button class="px-3 bg-rose-900/30 hover:bg-rose-600 text-rose-400 hover:text-white rounded transition text-xs border border-rose-900/50">🗑</button>
                 </div>
               </div>
             </div>
          </div>

          <!-- 模块 3：局内专属设定 (包含了剧情导向) -->
          <div v-if="store.rightTab === 'local_edit'" class="space-y-6 animate-[fadeIn_0.2s]">
             <div v-if="!store.sessionId" class="text-center text-slate-500 text-xs mt-10">未连接故事线</div>
             <template v-else>
               <div class="bg-indigo-900/20 border border-indigo-800/50 p-4 rounded-xl shadow-inner">
                 <h3 class="text-xs font-bold text-indigo-300 mb-2">🧭 主线剧情导向 (Plot Compass)</h3>
                 <p class="text-[10px] text-slate-400 mb-3 leading-relaxed">描述你想让故事如何发展。该设定将作为高优先级锚点持续影响 AI 偏好。</p>
                 <textarea v-model="store.localSettings.plotCompass" class="w-full h-24 bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs text-slate-300 outline-none focus:border-indigo-500 resize-none shadow-inner" placeholder="例如：放慢节奏，触发遭遇战..."></textarea>
               </div>
               <div class="border-t border-slate-700 pt-4 space-y-3">
                  <h3 class="text-xs font-bold text-slate-400 mb-3">👁️ 局内雷达功能覆盖</h3>
                  <label class="flex items-center justify-between text-xs text-slate-300 cursor-pointer bg-slate-800/50 px-3 py-2.5 rounded border border-slate-700 hover:border-slate-500 transition">
                    <span>🗺️ 启用本地图系统</span>
                    <input type="checkbox" v-model="store.localSettings.showMap" class="w-4 h-4 rounded bg-slate-900 border-slate-600 text-indigo-500">
                  </label>
                  <label class="flex items-center justify-between text-xs text-slate-300 cursor-pointer bg-slate-800/50 px-3 py-2.5 rounded border border-slate-700 hover:border-slate-500 transition">
                    <span>🕰️ 覆盖全局时间显示</span>
                    <select v-model="store.localSettings.showTime" class="bg-slate-900 border border-slate-600 rounded text-[10px] p-1 outline-none text-slate-300"><option :value="null">跟随全局</option><option :value="true">强制显示</option><option :value="false">强制隐藏</option></select>
                  </label>
               </div>
             </template>
          </div>
        </div>
      </aside>
    </div>

    <!-- ================= 全局弹窗：系统设置 (Settings) ================= -->
    <div v-if="store.modals.settings" class="fixed inset-0 bg-black/80 z-50 flex items-center justify-center backdrop-blur-sm p-4">
      <div class="bg-aw_panel border border-slate-600 rounded-2xl w-full max-w-3xl shadow-2xl flex flex-col slide-up overflow-hidden h-[75vh]">
        <div class="p-5 border-b border-slate-700 flex justify-between bg-slate-900/80"><h2 class="font-bold text-slate-200 text-xl">⚙️ 系统设置与模型核心</h2><button @click="store.modals.settings=false" class="text-slate-400 hover:text-white text-xl">✕</button></div>
        <div class="flex flex-1 overflow-hidden">
          <div class="w-48 bg-slate-900/50 border-r border-slate-700 p-3 space-y-1">
            <button class="w-full text-left px-3 py-2 text-sm font-bold bg-slate-800 text-emerald-400 rounded">🔌 API 配置</button>
            <button class="w-full text-left px-3 py-2 text-sm font-bold text-slate-400 hover:bg-slate-800 rounded">🎛️ 调试与沉浸</button>
            <button class="w-full text-left px-3 py-2 text-sm font-bold text-slate-400 hover:bg-slate-800 rounded">🧠 上下文记忆</button>
          </div>
          <div class="flex-1 p-6 overflow-y-auto space-y-8 bg-slate-800/20 custom-scrollbar">
            <!-- 设置内容，修复了上一版打不开的问题 -->
            <section>
              <h3 class="text-sm font-bold text-emerald-400 mb-3 border-b border-slate-700 pb-2">大语言模型配置 (LLM)</h3>
              <div class="space-y-3">
                <div><label class="text-xs font-bold text-slate-400 block mb-1">DeepSeek / OpenAI Key</label><input type="password" v-model="store.globalSettings.apiKey" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" placeholder="sk-..." /></div>
              </div>
            </section>
            <section>
              <h3 class="text-sm font-bold text-amber-400 mb-3 border-b border-slate-700 pb-2">图像引擎配置 (Image Gen)</h3>
              <div class="space-y-3">
                <div><label class="text-xs font-bold text-slate-400 block mb-1">ComfyUI / SD API 接口地址</label><input v-model="store.globalSettings.imageApiUrl" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" placeholder="http://127.0.0.1:8188" /></div>
                <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="store.settings.autoImage" class="rounded bg-slate-800 border-slate-600 text-emerald-500"><span>允许 AI 在适当场景自动触发异步生图</span></label>
              </div>
            </section>
            <section>
              <h3 class="text-sm font-bold text-rose-400 mb-4 border-b border-slate-700 pb-2">开发者调试选项 (Debug)</h3>
              <div class="grid grid-cols-2 gap-4">
                <label class="flex items-center gap-3 text-sm text-slate-400 cursor-pointer hover:text-slate-200"><input type="checkbox" v-model="store.settings.showFutures" class="rounded bg-slate-800 border-slate-600 text-rose-500"><span>显示未来可能性包 (N*n)</span></label>
                <label class="flex items-center gap-3 text-sm text-slate-400 cursor-pointer hover:text-slate-200"><input type="checkbox" v-model="store.settings.allowReroll" class="rounded bg-slate-800 border-slate-600 text-rose-500"><span>开启“重掷未来”</span></label>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>

    <!-- ================= 弹窗：创世 (New Game) ================= -->
    <div v-if="store.modals.newGame" class="fixed inset-0 bg-black/80 z-50 flex items-center justify-center backdrop-blur-sm p-4">
      <div class="bg-aw_panel border border-emerald-900/50 rounded-2xl w-full max-w-3xl shadow-2xl overflow-hidden flex flex-col slide-up">
        <div class="p-5 border-b border-slate-700 flex justify-between bg-slate-900/80"><h2 class="font-bold text-emerald-400 text-xl">✨ 创世协议</h2><button @click="store.modals.newGame=false" class="text-slate-400 hover:text-white text-2xl">✕</button></div>
        <div class="p-6 space-y-4">
          <div><label class="text-xs font-bold text-slate-400 block mb-1">📝 时间线命名</label><input class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none" placeholder="例如：废土远征纪" /></div>
          <div><label class="text-xs font-bold text-slate-400 block mb-1">👤 扮演角色 (Player Persona)</label><select v-model="store.selectedPlayerPersona" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none"><option>空白模板 (无名者)</option><option>流浪法师 A</option></select></div>
          <div class="grid grid-cols-2 gap-4">
             <div><label class="text-xs font-bold text-slate-400 block mb-1">🌍 世界书</label><select v-model="store.selectedWorldbook" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none"><option>无界域 (暂不加载)</option></select></div>
             <div><label class="text-xs font-bold text-slate-400 block mb-1">🎭 文风卡</label><select v-model="store.selectedStyle" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none"><option>默认 (无)</option></select></div>
          </div>
          <button class="w-full py-4 mt-2 bg-emerald-600 hover:bg-emerald-500 rounded-xl font-bold shadow-lg transition">降临新世界</button>
        </div>
      </div>
    </div>

    <!-- ================= 弹窗：中途安排角色登场 ================= -->
    <div v-if="store.modals.insertChar" class="fixed inset-0 bg-black/80 z-[60] flex items-center justify-center backdrop-blur-sm p-4">
      <div class="bg-aw_panel border border-indigo-900/50 rounded-2xl w-[500px] shadow-2xl flex flex-col slide-up overflow-hidden">
        <div class="p-4 border-b border-slate-700 flex justify-between bg-slate-900/80"><h2 class="font-bold text-indigo-400 text-lg">⬇️ 引入局内: {{ store.insertCharData.name }}</h2><button @click="store.modals.insertChar=false" class="text-slate-400 hover:text-white text-xl">✕</button></div>
        <div class="p-6 space-y-4">
          <p class="text-xs text-slate-400">AI 会根据你的描述自动安排他/她的出场方式。</p>
          <div>
            <label class="text-xs font-bold text-slate-300 block mb-2">如何登场 (Entrance Prompt)</label>
            <textarea v-model="store.insertCharData.entrance" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none focus:border-indigo-500 h-28 resize-none shadow-inner" placeholder="例如：突然踹开酒馆的大门，身上带着血迹向玩家求救..."></textarea>
          </div>
          <div class="flex justify-end gap-3 mt-4">
            <button @click="store.modals.insertChar=false" class="px-4 py-2 bg-slate-800 text-slate-300 rounded font-bold hover:bg-slate-700">取消</button>
            <button class="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded font-bold shadow-lg">发送指令</button>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<style>
.slide-up { animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
@keyframes slideUp { from { opacity: 0; transform: translateY(20px) scale(0.95); } to { opacity: 1; transform: translateY(0) scale(1); } }
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #475569; border-radius: 2px; }
</style>