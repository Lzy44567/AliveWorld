<script setup>
import { computed } from 'vue';
import { configStore } from '../../store/configStore';

const props = defineProps({ settings: { type: Object, required: true } });
const activeAdvanced = computed(() => [
  ['autoCompressMemory', '记忆压缩'],
  ['worldbookCaptureEnabled', '世界书捕获'],
  ['learnUserPreferences', '偏好学习'],
  ['deepPreferenceAnalysis', '偏好深度分析'],
  ['analyzeSensitivePreferences', '敏感偏好分析'],
  ['showCausalLedger', '因果账本调试'],
].filter(([key]) => props.settings[key]).map(([, label]) => label));
</script>

<template>
  <section class="mb-3 rounded-xl border border-slate-700 bg-slate-900/55 p-3">
    <label class="flex cursor-pointer items-center justify-between gap-4">
      <span class="min-w-0">
        <span class="block text-xs font-bold text-slate-200">显示高级设置</span>
        <span class="mt-1 block text-[10px] leading-relaxed text-slate-500">默认隐藏复杂选项；隐藏不会停用或重置已经启用的功能。</span>
      </span>
      <input v-model="configStore.uiPreferences.showAdvancedSettings" data-testid="advanced-settings-toggle" type="checkbox" class="h-4 w-4 shrink-0 accent-indigo-500">
    </label>
    <p v-if="!configStore.uiPreferences.showAdvancedSettings && activeAdvanced.length" class="mt-2 border-t border-slate-800 pt-2 text-[10px] text-amber-300/80">
      后台仍启用：{{ activeAdvanced.join('、') }}
    </p>
  </section>
</template>
