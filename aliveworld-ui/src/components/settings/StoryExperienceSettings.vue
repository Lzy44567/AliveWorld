<script setup>
import { computed } from 'vue';
import { configStore } from '../../store/configStore';
import StorySettingsGroups from './StorySettingsGroups.vue';

const settings = computed(() => configStore.story.settings);
</script>

<template>
  <section>
    <div class="mb-3">
      <h3 class="text-xs font-bold text-rose-300">🎛️ 当前故事体验</h3>
      <p class="mt-1 text-[10px] leading-relaxed text-slate-500">只覆盖当前故事。记忆、偏好、世界书捕获和调试功能归入默认折叠的高级分类。</p>
    </div>
    <StorySettingsGroups :settings="settings" show-memory-status />
  </section>
</template>
