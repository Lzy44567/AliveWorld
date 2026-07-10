<!-- src/components/modals/SettingsModal.vue -->
<script setup>
import { computed } from 'vue';
import { configStore } from '../../store/configStore';
import { uiStore } from '../../store/uiStore';
const close = () => { uiStore.modals.settings = false; };
const allEntityDisclosure = computed({
  get: () => ['showEntityNames', 'showEntityMotives', 'allowEntityEditing', 'showEntityBubbles'].every(key => configStore.settings[key]),
  set: value => {
    for (const key of ['showEntityNames', 'showEntityMotives', 'allowEntityEditing', 'showEntityBubbles']) configStore.settings[key] = value;
  }
});
</script>
<template>
  <div class="fixed inset-0 bg-black/80 z-50 flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-aw_panel border border-slate-600 rounded-2xl w-full max-w-3xl shadow-2xl flex flex-col slide-up overflow-hidden h-[80vh]">
      <div class="p-5 border-b border-slate-700 flex justify-between bg-slate-900/80">
        <h2 class="font-bold text-slate-200 text-xl">⚙️ 系统设置与模型核心</h2>
        <button @click="close" class="text-slate-400 hover:text-white text-xl">✕</button>
      </div>
      <div class="flex flex-1 overflow-hidden">
        <div class="w-48 bg-slate-900/50 border-r border-slate-700 p-3 space-y-1">
          <button class="w-full text-left px-3 py-2 text-sm font-bold bg-slate-800 text-emerald-400 rounded">🔌 API 配置</button>
          <button class="w-full text-left px-3 py-2 text-sm font-bold text-slate-400 hover:bg-slate-800 rounded">🎛️ 调试与推演</button>
        </div>
        <div class="flex-1 p-6 overflow-y-auto space-y-8 bg-slate-800/20 custom-scrollbar">
          <!-- 这里因为绑定了 configStore，修改即会自动触发下文我们要写的同步方法 -->
          <section>
            <h3 class="text-sm font-bold text-emerald-400 mb-3 border-b border-slate-700 pb-2">大语言模型配置 (实时生效)</h3>
            <div class="space-y-3">
              <div><label class="text-xs text-slate-400 block mb-1">API Base URL</label><input v-model="configStore.globalSettings.apiBaseUrl" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" /></div>
              <div><label class="text-xs text-slate-400 block mb-1">API Key (密钥)</label><input type="password" v-model="configStore.globalSettings.apiKey" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" /></div>
              <div><label class="text-xs text-slate-400 block mb-1">请求模型 (Model)</label><input v-model="configStore.globalSettings.model" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" /></div>
            </div>
          </section>
          
          <section>
            <h3 class="text-sm font-bold text-rose-400 mb-4 border-b border-slate-700 pb-2">推演与调试选项</h3>
            <div class="grid grid-cols-2 gap-4">
              <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.showFutures" class="rounded bg-slate-800 border-slate-600 text-rose-500"><span>显示未来可能性包 (N*n)</span></label>
              <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.showDice" class="rounded bg-slate-800 border-slate-600 text-rose-500"><span>显示命运掷骰结果</span></label>
              <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.allowReroll" class="rounded bg-slate-800 border-slate-600 text-rose-500"><span>开启“重掷未来”允许反悔</span></label>
              <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.aiSuggestions" class="rounded bg-slate-800 border-slate-600 text-rose-500"><span>开启 AI 行动灵感建议</span></label>
              <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.autoCompressMemory" class="rounded bg-slate-800 border-slate-600 text-indigo-500"><span>智能记忆压缩 (未实装)</span></label>
              <div class="col-span-2 border border-slate-700 rounded-lg p-3 space-y-3">
                <p class="text-sm font-bold text-amber-300">暗流实体显示（可自由组合）</p>
                <div class="grid grid-cols-2 gap-3">
                  <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="allEntityDisclosure" class="rounded bg-slate-800 border-slate-600 text-amber-500"><span>实体：全部</span></label>
                  <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.showEntityNames" class="rounded bg-slate-800 border-slate-600 text-amber-500"><span>显示名称</span></label>
                  <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.showEntityMotives" class="rounded bg-slate-800 border-slate-600 text-amber-500"><span>显示动机</span></label>
                  <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.allowEntityEditing" class="rounded bg-slate-800 border-slate-600 text-amber-500"><span>允许编辑</span></label>
                  <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.showEntityBubbles" class="rounded bg-slate-800 border-slate-600 text-amber-500"><span>显示气泡</span></label>
                </div>
                <p class="text-[10px] text-slate-500">气泡只显示获准的名称与动机；编辑权限不会自动公开完整幕后行动。</p>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>
