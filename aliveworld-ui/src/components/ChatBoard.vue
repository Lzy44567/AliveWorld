<!-- src/components/ChatBoard.vue -->
<script setup>
import { ref } from 'vue'
import { store } from '../store.js'

const userInput = ref("")
const lastAction = ref("")

const submitAction = async (forcedText = null) => {
  const text = forcedText || userInput.value.trim()
  if (!text || store.isProcessing || !store.sessionId) return
  
  store.chatLog.push({ role: "user", content: text })
  lastAction.value = text; userInput.value = ""
  store.isProcessing = true
  
  try {
    const res = await fetch(`http://127.0.0.1:8000/api/v1/game/${store.sessionId}/action`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: text })
    })
    if (res.ok) {
      const result = await res.json()
      store.chatLog.push(...result.chat_messages.filter(m => m.role !== 'user'))
      store.syncState(result.state)
      setTimeout(() => { const c = document.getElementById('chat-container'); if(c) c.scrollTop = c.scrollHeight }, 100)
    }
  } catch (error) {} finally { store.isProcessing = false }
}

// 占位：重新随机未来
const rerollFuture = () => {
  alert("(开发中) 将回退本回合大模型生成，重新进行命运掷骰，生成新结局！")
}
</script>

<template>
  <main class="flex-1 flex flex-col relative z-0 bg-aw_bg overflow-hidden">
    
    <div class="absolute inset-0 z-0 opacity-15 pointer-events-none transition-all duration-1000" v-if="store.sessionId">
      <img :src="store.currentScene.img" class="w-full h-full object-cover blur-md" alt="cg">
    </div>

    <!-- Galgame 立绘层 -->
    <div class="absolute bottom-0 right-12 z-0 pointer-events-none transition-all duration-700 ease-out" :class="store.isSpeakerActive ? 'opacity-90 translate-y-0' : 'opacity-0 translate-y-10'" v-if="store.sessionId">
      <div class="w-[450px] h-[650px] relative">
        <img :src="store.currentSpeakerSprite" class="w-full h-full object-cover rounded-t-full shadow-2xl" style="mask-image: linear-gradient(to top, transparent 10%, black 50%); -webkit-mask-image: linear-gradient(to top, transparent 5%, black 40%);">
      </div>
    </div>

    <!-- ================= 聊天气泡区 ================= -->
    <div class="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 pb-56 z-10 custom-scrollbar" id="chat-container">
      <div v-if="!store.sessionId" class="h-full flex items-center justify-center flex-col">
         <h2 class="text-4xl font-bold text-slate-300 mb-2 drop-shadow-lg tracking-widest">A L I V E W O R L D</h2>
         <p class="text-slate-400">请从右侧档案库唤醒一条时间线</p>
      </div>
      
      <template v-else>
        <div v-for="(msg, idx) in store.chatLog" :key="idx" class="flex flex-col" :class="msg.role === 'user' ? 'items-end' : 'items-start'">
          
          <!-- 🚀 增强：命运观测器 (Reactions Array) -->
          <div v-if="msg.role === 'reactions' && store.debugSettings.showFutures" class="w-full max-w-[85%] bg-amber-950/40 border border-amber-700/50 rounded-xl overflow-hidden backdrop-blur-md shadow-lg mb-2">
            <details class="group">
              <summary class="cursor-pointer px-4 py-2 text-xs text-amber-400 font-bold flex justify-between items-center hover:bg-amber-900/50 transition select-none">
                <span class="flex items-center gap-2"><span>🎲</span> 观测到 {{ msg.content.length || '多' }} 种可能的未来 (点击展开)</span>
                <span class="transform group-open:rotate-180 transition">▼</span>
              </summary>
              <div class="px-4 py-3 border-t border-amber-900/50 space-y-2">
                <div v-for="r in msg.content" :key="r.id" class="flex items-center gap-3 text-xs text-amber-200 bg-black/30 p-2 rounded">
                   <div class="w-10 text-center font-mono font-bold bg-amber-600/30 rounded px-1">{{ r.weight }}%</div>
                   <div class="flex-1">{{ r.description }}</div>
                </div>
              </div>
            </details>
          </div>

          <!-- 掷骰结果展示 -->
          <div v-else-if="msg.role === 'system' && store.debugSettings.showDiceResult" class="text-xs text-rose-400 mb-1 px-4 py-2 bg-rose-950/60 border border-rose-700/50 rounded-lg backdrop-blur-md italic shadow-md max-w-[85%] flex justify-between items-center group">
            <span>{{ store.formatContent(msg.content) }}</span>
            <button v-if="store.debugSettings.allowReroll" @click="rerollFuture" class="hidden group-hover:block px-2 py-0.5 bg-rose-800 hover:bg-rose-600 text-white rounded text-[10px] font-bold transition ml-4">
              🔄 重掷未来
            </button>
          </div>

          <!-- 玩家与 AI 对话正文 -->
          <div v-else-if="msg.role === 'user' || msg.role === 'ai'" class="max-w-[85%] rounded-2xl p-5 whitespace-pre-wrap leading-relaxed shadow-2xl text-[15px] backdrop-blur-md" 
               :class="msg.role === 'user' ? 'bg-indigo-600/90 text-white rounded-br-sm' : 'bg-slate-900/85 border border-slate-600 text-slate-200 rounded-bl-sm'" 
               v-text="store.formatContent(msg.content)"></div>
        </div>

        <!-- 异步加载与处理提示 -->
        <div v-if="store.isProcessing" class="flex flex-col gap-2">
          <div class="text-emerald-400 text-sm font-bold italic animate-pulse">🧠 主引擎双轨推演中...</div>
          <div class="text-amber-500 text-xs font-mono italic opacity-70 ml-6">└─ [暗流引擎] 实体正在演算阴谋...</div>
        </div>
      </template>
    </div>

    <!-- ================= 底部输入区 ================= -->
    <div class="absolute bottom-0 w-full p-6 bg-gradient-to-t from-aw_bg via-aw_bg/95 to-transparent z-20">
      <div class="max-w-4xl mx-auto flex flex-col gap-3">
        
        <!-- 灵感建议按钮 -->
        <div class="flex gap-2 px-1 mb-1 overflow-x-auto custom-scrollbar" v-if="store.sessionId && !store.isProcessing && store.debugSettings.aiSuggestions">
          <button v-for="(sug, idx) in store.aiSuggestions" :key="idx" @click="submitAction(sug)" class="px-4 py-2 text-xs font-bold bg-slate-800/80 hover:bg-emerald-600/80 text-slate-300 hover:text-white border border-slate-600 hover:border-emerald-500 rounded-full transition whitespace-nowrap backdrop-blur-md shadow-lg">
            💡 {{ sug }}
          </button>
        </div>

        <div class="relative flex gap-3 drop-shadow-2xl">
          <input v-model="userInput" @keyup.enter="submitAction()" :disabled="store.isProcessing || !store.sessionId" class="flex-1 bg-slate-900/90 border border-slate-600 rounded-xl px-5 py-4 outline-none focus:border-indigo-500 text-slate-100 placeholder-slate-500 shadow-inner text-base backdrop-blur" placeholder="输入你的抉择..." />
          <button @click="submitAction()" :disabled="store.isProcessing || !store.sessionId" class="px-8 py-4 bg-emerald-600 hover:bg-emerald-500 rounded-xl font-bold disabled:opacity-50 transition shadow-lg text-lg">发送</button>
        </div>
      </div>
    </div>
  </main>
</template>