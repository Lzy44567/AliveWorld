<script setup>
import { ref } from 'vue';
import { gameApi } from '../../api/gameApi';
import { configStore } from '../../store/configStore';
import { gameStore } from '../../store/gameStore';
import { uiStore } from '../../store/uiStore';

const saving = ref(false);

const toggle = async () => {
  if (!gameStore.sessionId || saving.value) return;
  const previous = configStore.story.settings.entitiesEnabled;
  configStore.story.settings.entitiesEnabled = !previous;
  saving.value = true;
  try {
    await gameApi.updateStoryConfig(gameStore.sessionId, {
      world_premise: configStore.story.worldPremise,
      plot_compass: configStore.story.plotCompass,
      story_settings: configStore.story.settings
    });
  } catch (error) {
    configStore.story.settings.entitiesEnabled = previous;
    uiStore.showToast('暗流推演开关保存失败', 'error');
  } finally {
    saving.value = false;
  }
};
</script>

<template>
  <button v-if="gameStore.sessionId" @click="toggle" role="switch" :aria-checked="configStore.story.settings.entitiesEnabled" :disabled="saving" class="inline-flex items-center gap-2 rounded-full border px-2 py-1 text-[10px] font-bold transition disabled:opacity-50" :class="configStore.story.settings.entitiesEnabled ? 'border-purple-600/70 bg-purple-950/40 text-purple-300' : 'border-slate-600 bg-slate-800 text-slate-400'" :title="configStore.story.settings.entitiesEnabled ? '点击暂停暗流实体推演' : '点击启用暗流实体推演'">
    <span class="flex h-4 w-7 items-center rounded-full p-0.5" :class="configStore.story.settings.entitiesEnabled ? 'justify-end bg-purple-500' : 'justify-start bg-slate-600'">
      <span class="h-3 w-3 rounded-full bg-white shadow" />
    </span>
    {{ configStore.story.settings.entitiesEnabled ? '运行' : '暂停' }}
  </button>
</template>
