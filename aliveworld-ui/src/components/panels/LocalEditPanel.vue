<script setup>
import { ref } from 'vue';
import { gameStore } from '../../store/gameStore';
import { configStore } from '../../store/configStore';
import { uiStore } from '../../store/uiStore';
import { gameApi } from '../../api/gameApi';
import StoryExperienceSettings from '../settings/StoryExperienceSettings.vue';

const saving = ref(false);

const saveStoryConfig = async () => {
  if (!gameStore.sessionId || saving.value) return;
  saving.value = true;
  try {
    const data = await gameApi.updateStoryConfig(gameStore.sessionId, {
      world_premise: configStore.story.worldPremise,
      plot_compass: configStore.story.plotCompass,
      story_settings: configStore.story.settings
    });
    configStore.applyStoryConfig(data);
    uiStore.showToast('本局设置已保存');
  } catch (error) {
    uiStore.showToast('本局设置保存失败', 'error');
  } finally {
    saving.value = false;
  }
};

const restoreDefaults = async () => {
  configStore.restoreStoryDefaults();
  await saveStoryConfig();
};
</script>

<template>
  <div class="space-y-5 animate-[fadeIn_0.2s] pb-6">
    <div v-if="!gameStore.sessionId" class="text-center text-slate-500 text-xs mt-10">未连接时间线</div>
    <template v-else>
      <section class="bg-emerald-950/20 border border-emerald-800/50 p-4 rounded-xl">
        <h3 class="text-xs font-bold text-emerald-300 mb-2">🌌 宇宙主导向简述</h3>
        <p class="text-[10px] text-slate-400 mb-3">当前故事的基础世界观与开局前提；可代替一份简单世界书。</p>
        <textarea v-model="configStore.story.worldPremise" class="story-textarea" placeholder="例如：现代都市中隐藏着少量超能力者……"></textarea>
      </section>

      <section class="bg-indigo-950/20 border border-indigo-800/50 p-4 rounded-xl">
        <h3 class="text-xs font-bold text-indigo-300 mb-2">🧭 主线剧情导向（Plot Compass）</h3>
        <p class="text-[10px] text-slate-400 mb-3">指导接下来正文和随机选项的倾向，不会覆盖宇宙设定。</p>
        <textarea v-model="configStore.story.plotCompass" class="story-textarea" placeholder="例如：近期逐渐揭示导师的欺骗，但不要立刻揭露真相……"></textarea>
      </section>

      <StoryExperienceSettings />

      <div class="flex gap-2 sticky bottom-0 bg-slate-900/95 border border-slate-700 rounded-xl p-3 shadow-xl">
        <button @click="restoreDefaults" :disabled="saving" class="px-3 py-2 text-xs text-slate-300 bg-slate-800 hover:bg-slate-700 rounded-lg disabled:opacity-50">恢复全局默认</button>
        <button @click="saveStoryConfig" :disabled="saving" class="flex-1 px-3 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg disabled:opacity-50">{{ saving ? '保存中…' : '保存本局设置' }}</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.story-textarea { width: 100%; height: 6rem; resize: none; border: 1px solid rgb(51 65 85); border-radius: .5rem; background: rgb(15 23 42); padding: .75rem; font-size: .75rem; color: rgb(203 213 225); outline: none; }
.story-textarea:focus { border-color: rgb(99 102 241); }
</style>
