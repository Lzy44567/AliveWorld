<!-- src/components/modals/AllModals.vue -->
<script setup>
import { uiStore } from '../../store/uiStore';
import TerminalModal from './TerminalModal.vue';
import AssetEditorModal from './AssetEditorModal.vue';
import WorldbookWorkshopModal from './WorldbookWorkshopModal.vue';
import EmbeddingModelModal from './EmbeddingModelModal.vue';
import SettingsModal from './SettingsModal.vue';
import NewGameModal from './NewGameModal.vue';
import InsertCharModal from './InsertCharModal.vue';
import GalleryModal from './GalleryModal.vue';
import ImageGeneratorModal from './ImageGeneratorModal.vue';
import CausalLedgerModal from './CausalLedgerModal.vue';
</script>

<template>
  <SettingsModal v-if="uiStore.modals.settings" />
  <NewGameModal v-if="uiStore.modals.newGame" />
  <InsertCharModal v-if="uiStore.modals.insertChar" />
  <GalleryModal v-if="uiStore.modals.gallery" />
  <ImageGeneratorModal v-if="uiStore.modals.imageGenerator" />
  <TerminalModal v-if="uiStore.modals.terminal" />
  <AssetEditorModal v-if="uiStore.modals.assetEditor" />
  <WorldbookWorkshopModal v-if="uiStore.modals.worldbookWorkshop" />
  <EmbeddingModelModal v-if="uiStore.modals.embeddingModel" />
  <CausalLedgerModal v-if="uiStore.modals.causalLedger" />
</template>
