import { onUnmounted, ref, watch } from 'vue';
import { gameApi } from '../api/gameApi';
import { configStore } from '../store/configStore';
import { gameStore } from '../store/gameStore';

export function useStoryConfigAutosave(delay = 600) {
  const saveState = ref('saved');
  let timer = null;

  const persist = async () => {
    if (!gameStore.sessionId || !configStore.story.active) return;
    saveState.value = 'saving';
    try {
      await gameApi.updateStoryConfig(gameStore.sessionId, {
        world_premise: configStore.story.worldPremise,
        plot_compass: configStore.story.plotCompass,
        story_settings: configStore.story.settings
      });
      saveState.value = 'saved';
    } catch (error) {
      saveState.value = 'error';
    }
  };

  const stop = watch(
    () => configStore.story,
    () => {
      if (!configStore.story.active) return;
      saveState.value = 'pending';
      clearTimeout(timer);
      timer = setTimeout(persist, delay);
    },
    { deep: true }
  );

  onUnmounted(() => {
    stop();
    clearTimeout(timer);
    if (saveState.value === 'pending') persist();
  });

  return { saveState, persist };
}
