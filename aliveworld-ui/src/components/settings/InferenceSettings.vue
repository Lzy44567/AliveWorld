<script setup>
import { configStore } from '../../store/configStore';
import EntityDisclosureSettings from './EntityDisclosureSettings.vue';
</script>

<template>
  <section>
    <h3 class="text-sm font-bold text-rose-400 mb-1 border-b border-slate-700 pb-2">新故事的默认体验</h3>
    <p class="text-[10px] text-slate-500 mb-4">创建新存档时复制这些默认值；已有故事请在“局内专属设置”中单独修改。</p>
    <div class="grid grid-cols-2 gap-4">
      <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.showFutures" class="rounded bg-slate-800 border-slate-600 text-rose-500"><span>显示动态未来候选</span></label>
      <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.showDice" class="rounded bg-slate-800 border-slate-600 text-rose-500"><span>显示命运掷骰结果</span></label>
      <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.allowReroll" class="rounded bg-slate-800 border-slate-600 text-rose-500"><span>开启“重掷未来”允许反悔</span></label>
      <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.aiSuggestions" class="rounded bg-slate-800 border-slate-600 text-rose-500"><span>开启 AI 行动灵感建议</span></label>
      <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.showTime" class="rounded bg-slate-800 border-slate-600 text-cyan-500"><span>新故事默认显示世界时间</span></label>
      <label class="flex items-center gap-3 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.autoCompressMemory" class="rounded bg-slate-800 border-slate-600 text-indigo-500"><span>自动压缩故事记忆</span></label>
      <EntityDisclosureSettings />
    </div>
  </section>
</template>
