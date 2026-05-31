<!-- src/components/modals/AllModals.vue -->
<script setup>
import { uiStore } from '../../store/uiStore';
import TerminalModal from './TerminalModal.vue';
import AssetEditorModal from './AssetEditorModal.vue';
import SettingsModal from './SettingsModal.vue';
import NewGameModal from './NewGameModal.vue';
import InsertCharModal from './InsertCharModal.vue';
import GalleryModal from './GalleryModal.vue';
</script>

<template>
  <SettingsModal v-if="uiStore.modals.settings" />
  <NewGameModal v-if="uiStore.modals.newGame" />
  <InsertCharModal v-if="uiStore.modals.insertChar" />
  <GalleryModal v-if="uiStore.modals.gallery" />
  <TerminalModal v-if="uiStore.modals.terminal" />
  <AssetEditorModal v-if="uiStore.modals.assetEditor" />
</template>