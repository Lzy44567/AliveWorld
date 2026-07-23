<script setup>
import WorkshopAssetBrowser from './WorkshopAssetBrowser.vue';
import WorkshopConversation from './WorkshopConversation.vue';
import WorkshopDraftSidebar from './WorkshopDraftSidebar.vue';
</script>

<template>
  <div class="flex min-h-0 flex-1 overflow-hidden">
    <WorkshopDraftSidebar />
    <WorkshopConversation />
    <WorkshopAssetBrowser />
  </div>
</template>
