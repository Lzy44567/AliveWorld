<!-- src/components/modals/GalleryModal.vue -->
<script setup>
import { uiStore } from '../../store/uiStore';
const close = () => { uiStore.modals.gallery = false; };
</script>
<template>
  <div class="fixed inset-0 bg-black/80 z-[70] flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-aw_panel border border-slate-600 rounded-xl w-full max-w-5xl shadow-2xl flex flex-col slide-up overflow-hidden h-[80vh]">
      <div class="p-4 border-b border-slate-700 flex justify-between bg-slate-900/80">
        <h2 class="font-bold text-amber-400 text-lg flex items-center gap-2">🖼️ 回忆画廊</h2><button @click="close" class="text-slate-400 hover:text-white text-xl">✕</button>
      </div>
      <div class="flex-1 p-6 overflow-y-auto bg-slate-900/30">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="aspect-square bg-slate-800 rounded-lg border border-slate-700 overflow-hidden group cursor-pointer relative">
            <img src="https://images.unsplash.com/photo-1542204625-236b284e366d?q=80&w=400&auto=format&fit=crop" class="w-full h-full object-cover opacity-70 group-hover:opacity-100 group-hover:scale-110 transition duration-500">
          </div>
        </div>
      </div>
    </div>
  </div>
</template>