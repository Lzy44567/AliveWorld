<script setup>
import { uiStore } from '../../store/uiStore';

function viewUpdate() {
  uiStore.settingsSection = 'updates';
  uiStore.modals.settings = true;
  uiStore.updateNotice.show = false;
}

function snooze() {
  const version = uiStore.updateNotice.result?.latest_version || '';
  if (version) sessionStorage.setItem('aw_update_snoozed_version', version);
  uiStore.updateNotice.show = false;
}
</script>

<template>
  <aside
    v-if="uiStore.updateNotice.show && uiStore.updateNotice.result"
    data-testid="startup-update-notice"
    class="fixed left-1/2 top-14 z-[75] flex w-[min(92vw,680px)] -translate-x-1/2 items-center justify-between gap-4 rounded-xl border border-cyan-700/80 bg-slate-900/95 px-4 py-3 shadow-2xl backdrop-blur"
    role="status"
  >
    <div class="min-w-0">
      <p class="font-bold text-cyan-200">发现新版本 {{ uiStore.updateNotice.result.latest_version }}</p>
      <p class="mt-0.5 truncate text-xs text-slate-400">检查与下载不会上传存档、资产或 API Key。</p>
    </div>
    <div class="flex shrink-0 gap-2">
      <button type="button" class="rounded-md border border-slate-600 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800" @click="snooze">稍后</button>
      <button type="button" class="rounded-md bg-cyan-700 px-3 py-1.5 text-xs font-bold text-white hover:bg-cyan-600" @click="viewUpdate">查看更新</button>
    </div>
  </aside>
</template>

