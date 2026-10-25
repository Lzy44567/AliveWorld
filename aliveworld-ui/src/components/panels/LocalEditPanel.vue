<script setup>
import { gameStore } from '../../store/gameStore';
import { configStore } from '../../store/configStore';
import { useStoryConfigAutosave } from '../../composables/useStoryConfigAutosave';
import StoryExperienceSettings from '../settings/StoryExperienceSettings.vue';
import ExpandableTextarea from '../common/ExpandableTextarea.vue';

const { saveState } = useStoryConfigAutosave();

const restoreDefaults = () => {
  configStore.restoreStoryDefaults();
};
</script>

<template>
  <div class="min-h-0 flex-1 space-y-5 overflow-y-auto pr-1 animate-[fadeIn_0.2s] pb-6 custom-scrollbar">
    <div v-if="!gameStore.sessionId" class="text-center text-slate-500 text-xs mt-10">未连接时间线</div>
    <template v-else>
      <section class="bg-emerald-950/20 border border-emerald-800/50 p-4 rounded-xl">
        <h3 class="text-xs font-bold text-emerald-300 mb-2">故事与世界概述</h3>
        <p class="text-[10px] text-slate-400 mb-3">当前故事的基础世界观与开局前提；可代替一份简单世界书。</p>
        <ExpandableTextarea v-model="configStore.story.worldPremise" label="故事与世界概述" textarea-class="story-textarea" placeholder="例如：现代都市中隐藏着少量超能力者……" />
      </section>

      <section class="bg-indigo-950/20 border border-indigo-800/50 p-4 rounded-xl">
        <h3 class="text-xs font-bold text-indigo-300 mb-2">🧭 剧情发展方向</h3>
        <p class="text-[10px] text-slate-400 mb-3">希望故事逐步走向哪里？保存后从下一次推进或重写生效，供未来与正文参考；不会改写既成事实或替你作出选择。留空则自由发展。</p>
        <ExpandableTextarea v-model="configStore.story.plotCompass" label="剧情发展方向" textarea-class="story-textarea" placeholder="例如：从陌生城市的求生逐步发展到建立自己的伙伴团队。" />
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
:deep(.story-textarea) { width: 100%; height: 6rem; resize: none; border: 1px solid rgb(51 65 85); border-radius: .5rem; background: rgb(15 23 42); padding: .75rem; font-size: .75rem; color: rgb(203 213 225); outline: none; }
:deep(.story-textarea:focus) { border-color: rgb(99 102 241); }
</style>
