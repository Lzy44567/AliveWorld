<script setup>
import { gameStore } from '../../store/gameStore';
import { configStore } from '../../store/configStore';
import { useStoryConfigAutosave } from '../../composables/useStoryConfigAutosave';
import StoryExperienceSettings from '../settings/StoryExperienceSettings.vue';

const { saveState } = useStoryConfigAutosave();

const restoreDefaults = () => {
  configStore.restoreStoryDefaults();
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
        <p class="text-[10px] text-slate-400 mb-3">用于描述整个故事的剧情风格与发展风格。当前版本仅保存草案，具体推演逻辑将在后续版本单独设计。</p>
        <textarea v-model="configStore.story.plotCompass" class="story-textarea" placeholder="例如：整体采用缓慢揭密、人物关系逐步反转的发展风格……"></textarea>
      </section>

      <StoryExperienceSettings />

      <div class="flex items-center justify-between sticky bottom-0 bg-slate-900/95 border border-slate-700 rounded-xl p-3 shadow-xl">
        <button @click="restoreDefaults" class="px-3 py-2 text-xs text-slate-300 bg-slate-800 hover:bg-slate-700 rounded-lg">恢复全局默认</button>
        <span class="text-[10px]" :class="saveState === 'error' ? 'text-rose-400' : saveState === 'saved' ? 'text-emerald-400' : 'text-amber-300'">
          {{ saveState === 'error' ? '自动保存失败' : saveState === 'saved' ? '已自动保存' : saveState === 'saving' ? '正在保存…' : '等待自动保存…' }}
        </span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.story-textarea { width: 100%; height: 6rem; resize: none; border: 1px solid rgb(51 65 85); border-radius: .5rem; background: rgb(15 23 42); padding: .75rem; font-size: .75rem; color: rgb(203 213 225); outline: none; }
.story-textarea:focus { border-color: rgb(99 102 241); }
</style>
