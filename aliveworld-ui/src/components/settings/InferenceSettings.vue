<script setup>
import { configStore } from '../../store/configStore';
import StorySettingsGroups from './StorySettingsGroups.vue';
</script>

<template>
  <section>
    <h3 class="border-b border-slate-700 pb-2 text-sm font-bold text-rose-400">新故事的默认体验</h3>
    <p class="mb-4 mt-2 text-[10px] leading-relaxed text-slate-500">创建新存档时复制这些默认值；已有故事请在“局内专属设置”修改。全局与局内使用相同名称和说明。</p>
    <StorySettingsGroups :settings="configStore.settings" />
  </section>
</template>
