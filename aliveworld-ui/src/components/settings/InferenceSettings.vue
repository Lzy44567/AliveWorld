<script setup>
import { configStore } from '../../store/configStore';
import EntityDisclosureSettings from './EntityDisclosureSettings.vue';
</script>

<template>
  <section>
    <h3 class="text-sm font-bold text-rose-400 mb-4 border-b border-slate-700 pb-2">推演与调试选项</h3>
    <div class="grid grid-cols-2 gap-4">
      <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.showFutures" class="rounded bg-slate-800 border-slate-600 text-rose-500"><span>显示未来可能性包 (N*n)</span></label>
      <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.showDice" class="rounded bg-slate-800 border-slate-600 text-rose-500"><span>显示命运掷骰结果</span></label>
      <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.allowReroll" class="rounded bg-slate-800 border-slate-600 text-rose-500"><span>开启“重掷未来”允许反悔</span></label>
      <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.aiSuggestions" class="rounded bg-slate-800 border-slate-600 text-rose-500"><span>开启 AI 行动灵感建议</span></label>
      <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.autoCompressMemory" class="rounded bg-slate-800 border-slate-600 text-indigo-500"><span>智能记忆压缩 (未实装)</span></label>
      <EntityDisclosureSettings />
    </div>
  </section>
</template>
