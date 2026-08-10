<script setup>
import { onBeforeUnmount, onMounted } from 'vue';
import { assetStore } from './store/assetStore'; // 引入 assetStore
import TopNav from './components/layout/TopNav.vue';
import LeftRadar from './components/layout/LeftRadar.vue';
import ChatBoard from './components/chat/ChatBoard.vue';
import RightDrawer from './components/layout/RightDrawer.vue';
import AllModals from './components/modals/AllModals.vue';
import ToastNotice from './components/common/ToastNotice.vue';
import UpdateNotice from './components/common/UpdateNotice.vue';
import WorkshopWorkspace from './components/workshop/WorkshopWorkspace.vue';
import { uiStore } from './store/uiStore';
import { configStore, waitForSystemConfig } from './store/configStore';
import { onboardingStore } from './store/onboardingStore';
import { updateApi } from './api/updateApi';

// [新增] 界面挂载时自动拉取数据
let assetRefreshTimer = null;
let updateCheckTimer = null;
onMounted(async () => {
  await assetStore.fetchAssets();
  const configLoaded = await waitForSystemConfig();
  if (configLoaded && !configStore.globalSettings.apiReady) {
    uiStore.apiSetupRequired = true;
    uiStore.settingsSection = 'api';
    uiStore.modals.settings = true;
  }
  let migrationPrompted = false;
  try {
    const response = await fetch('/api/v1/lobby/migration/legacy/status');
    if (response.ok) {
      const status = await response.json();
      if (status.should_prompt) {
        uiStore.legacyMigrationSource = status.source_root || '';
        if (uiStore.apiSetupRequired) {
          uiStore.pendingLegacyMigration = true;
        } else {
          uiStore.modals.legacyMigration = true;
        }
        migrationPrompted = true;
      }
    }
  } catch (_) { /* 迁移提示不能阻止游戏主界面加载 */ }
  if (configLoaded && !uiStore.apiSetupRequired && !migrationPrompted) onboardingStore.offerStory();
  // Assets may also arrive through migration or external file management.
  assetRefreshTimer = window.setInterval(() => assetStore.fetchAssets(), 5000);
  // Update discovery must never delay API setup, migration, story loading, or offline play.
  updateCheckTimer = window.setTimeout(async () => {
    try {
      const result = await updateApi.check(true);
      const snoozed = sessionStorage.getItem('aw_update_snoozed_version');
      if (result.update_available && result.latest_version !== snoozed) {
        uiStore.updateNotice.result = result;
        uiStore.updateNotice.show = true;
      }
    } catch (_) { /* GitHub unavailable: stay silent and keep the game usable. */ }
  }, 1800);
});
onBeforeUnmount(() => {
  if (assetRefreshTimer) window.clearInterval(assetRefreshTimer);
  if (updateCheckTimer) window.clearTimeout(updateCheckTimer);
});
</script>
<!-- 模板部分完全不用动 -->

<!-- src/App.vue (template 部分) -->
<template>
  <div class="h-screen w-screen flex flex-col bg-aw_bg text-slate-200 overflow-hidden font-sans selection:bg-indigo-500/30 relative">
    
    <TopNav />

    <div v-if="uiStore.appMode === 'game'" class="flex-1 flex overflow-hidden relative">
      <LeftRadar />
      <ChatBoard />
      <RightDrawer />
    </div>
    <WorkshopWorkspace v-else />

    <AllModals />
    
    <ToastNotice />
    <UpdateNotice />
  </div>
</template>

<style>
.slide-up { animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
@keyframes slideUp { from { opacity: 0; transform: translateY(20px) scale(0.95); } to { opacity: 1; transform: translateY(0) scale(1); } }
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #475569; border-radius: 2px; }
</style>
