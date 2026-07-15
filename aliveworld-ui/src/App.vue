<script setup>
import { onMounted } from 'vue';
import { assetStore } from './store/assetStore'; // 引入 assetStore
import TopNav from './components/layout/TopNav.vue';
import LeftRadar from './components/layout/LeftRadar.vue';
import ChatBoard from './components/chat/ChatBoard.vue';
import RightDrawer from './components/layout/RightDrawer.vue';
import AllModals from './components/modals/AllModals.vue';
import ToastNotice from './components/common/ToastNotice.vue';

// [新增] 界面挂载时自动拉取数据
onMounted(() => {
  assetStore.fetchAssets();
});
</script>
<!-- 模板部分完全不用动 -->

<!-- src/App.vue (template 部分) -->
<template>
  <div class="h-screen w-screen flex flex-col bg-aw_bg text-slate-200 overflow-hidden font-sans selection:bg-indigo-500/30 relative">
    
    <TopNav />

    <div class="flex-1 flex overflow-hidden relative">
      <LeftRadar />
      <ChatBoard />
      <RightDrawer />
    </div>

    <AllModals />
    
    <ToastNotice />
  </div>
</template>

<style>
.slide-up { animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
@keyframes slideUp { from { opacity: 0; transform: translateY(20px) scale(0.95); } to { opacity: 1; transform: translateY(0) scale(1); } }
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #475569; border-radius: 2px; }
</style>
