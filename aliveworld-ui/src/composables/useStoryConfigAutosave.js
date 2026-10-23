import { onUnmounted, ref, watch } from 'vue';
import { gameApi } from '../api/gameApi';
import { configStore } from '../store/configStore';
import { gameStore } from '../store/gameStore';

export function useStoryConfigAutosave(delay = 600) {
  const saveState = ref('saved');
  let timer = null;
  let queued = null;

  const snapshot = () => ({
    sessionId: gameStore.sessionId,
    payload: {
      world_premise: configStore.story.worldPremise,
      plot_compass: configStore.story.plotCompass,
      story_settings: { ...configStore.story.settings },
    },
  });

  const persist = async (pending = queued || snapshot()) => {
    if (!pending.sessionId || !configStore.story.active) return;
    const context = gameStore.contextFor(pending.sessionId);
    if (context?.isProcessing) {
      clearTimeout(timer);
      timer = setTimeout(() => persist(pending), delay);
      return;
    }
    saveState.value = 'saving';
    try {
      const result = await gameApi.updateStoryConfig(pending.sessionId, pending.payload);
      if (context) context.storyConfig = { ...(context.storyConfig || {}), ...result };
      if (queued === pending) queued = null;
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
      queued = snapshot();
      timer = setTimeout(() => persist(queued), delay);
    },
    { deep: true }
  );

  onUnmounted(() => {
    stop();
    clearTimeout(timer);
    if (saveState.value === 'pending' && queued) persist(queued);
  });

  return { saveState, persist };
}
