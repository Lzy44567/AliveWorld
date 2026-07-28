import { reactive } from 'vue';
import { assetStore } from './assetStore';
import { gameStore } from './gameStore';
import { uiStore } from './uiStore';

const STORAGE_KEY = 'aw_onboarding_v1';

function readState() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    return {
      completed: Boolean(parsed.completed),
      disabled: Boolean(parsed.disabled),
    };
  } catch (_) {
    return { completed: false, disabled: false };
  }
}

const persisted = readState();

export const onboardingStore = reactive({
  completed: persisted.completed,
  disabled: persisted.disabled,
  snoozedThisSession: false,

  persist() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      completed: this.completed,
      disabled: this.disabled,
    }));
  },

  async offerStory({ force = false } = {}) {
    await assetStore.fetchAssets();
    if (!force && (gameStore.sessionId || assetStore.saves.length)) {
      this.complete();
      return false;
    }
    if (!force && (this.completed || this.disabled || this.snoozedThisSession)) return false;
    uiStore.modals.quickStart = true;
    return true;
  },

  snooze() {
    this.snoozedThisSession = true;
    uiStore.modals.quickStart = false;
  },

  disable() {
    this.disabled = true;
    this.persist();
    uiStore.modals.quickStart = false;
  },

  complete() {
    this.completed = true;
    this.persist();
    uiStore.modals.quickStart = false;
  },

  restart() {
    this.completed = false;
    this.disabled = false;
    this.snoozedThisSession = false;
    this.persist();
    return this.offerStory({ force: true });
  },

  openNewGame({ starter = false } = {}) {
    const baseName = starter ? '边境苏醒' : '';
    let name = baseName;
    let suffix = 2;
    const existing = new Set(assetStore.saves.map(item => item.name));
    while (name && existing.has(name)) name = `${baseName}${suffix++}`;
    uiStore.newGamePrefill = {
      name,
      worldPremise: starter
        ? '这是一个开放的奇幻起点：我在一座边境城市醒来，城外沉寂多年的旧遗迹近日重新发光，各方势力尚未决定如何行动。不要替我规定唯一主线；我可以调查遗迹、结识当地人、离开城市或追求自己的目标，世界应根据我的选择继续变化。'
        : '',
      fromOnboarding: true,
    };
    uiStore.modals.quickStart = false;
    uiStore.modals.newGame = true;
  },
});
