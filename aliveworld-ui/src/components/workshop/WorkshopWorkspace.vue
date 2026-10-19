<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';
import WorkshopAssetBrowser from './WorkshopAssetBrowser.vue';
import WorkshopConversation from './WorkshopConversation.vue';
import WorkshopDraftSidebar from './WorkshopDraftSidebar.vue';
const focused = ref(false);
const exitFocus = event => { if (event.key === 'Escape') focused.value = false; };
onMounted(() => window.addEventListener('keydown', exitFocus));
onBeforeUnmount(() => window.removeEventListener('keydown', exitFocus));
</script>

<template>
  <div class="flex min-h-0 flex-1 overflow-hidden">
    <WorkshopDraftSidebar v-show="!focused" />
    <WorkshopConversation :focused="focused" @toggle-focus="focused = !focused" />
    <WorkshopAssetBrowser v-show="!focused" />
  </div>
</template>
