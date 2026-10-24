<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue';
import { workshopStore } from '../../store/workshopStore';
import { uiStore } from '../../store/uiStore';
import WorkshopAssetBrowser from './WorkshopAssetBrowser.vue';
import WorkshopConversation from './WorkshopConversation.vue';
import WorkshopDraftSidebar from './WorkshopDraftSidebar.vue';
const focused = ref(false);
const query = window.matchMedia('(max-width: 1100px)');
const narrow = ref(query.matches), panel = ref('');
const resize = () => { narrow.value = query.matches; panel.value = ''; };
const openPanel = name => {
  panel.value = panel.value === name ? '' : name;
  if (name === 'draft') uiStore.leftDrawerOpen = true;
  else uiStore.rightDrawerOpen = true;
};
watch(() => workshopStore.workshopId, () => { panel.value = ''; });
const exitFocus = event => { if (event.key === 'Escape') { if (panel.value) panel.value = ''; else focused.value = false; } };
onMounted(() => window.addEventListener('keydown', exitFocus));
onBeforeUnmount(() => window.removeEventListener('keydown', exitFocus));
onMounted(() => query.addEventListener('change', resize));
onBeforeUnmount(() => query.removeEventListener('change', resize));
</script>

<template>
  <div class="relative flex min-h-0 flex-1 flex-col overflow-hidden">
    <div v-if="narrow && !focused" class="flex shrink-0 gap-3 border-b border-slate-800 bg-slate-950 px-3 py-1 text-xs text-cyan-300"><button @click="openPanel('draft')">{{ panel === 'draft' ? '收起草稿' : '查看草稿' }}</button><button @click="openPanel('assets')">{{ panel === 'assets' ? '收起资产' : '选择资产' }}</button></div>
    <div class="relative flex min-h-0 flex-1 overflow-hidden">
    <WorkshopDraftSidebar v-show="!focused && (!narrow || panel === 'draft')" :class="narrow ? '!absolute inset-y-0 left-0 z-30 max-w-full' : ''" />
    <WorkshopConversation :focused="focused" @toggle-focus="focused = !focused" />
    <WorkshopAssetBrowser v-show="!focused && (!narrow || panel === 'assets')" :class="narrow ? '!absolute inset-y-0 right-0 z-30 max-w-full' : ''" />
    </div>
  </div>
</template>
