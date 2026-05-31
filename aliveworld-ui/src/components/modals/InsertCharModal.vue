<!-- src/components/modals/InsertCharModal.vue -->
<script setup>
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';
const close = () => { uiStore.modals.insertChar = false; };
</script>
<template>
  <div class="fixed inset-0 bg-black/80 z-[60] flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-aw_panel border border-indigo-900/50 rounded-2xl w-[500px] shadow-2xl flex flex-col slide-up overflow-hidden">
      <div class="p-4 border-b border-slate-700 flex justify-between bg-slate-900/80"><h2 class="font-bold text-indigo-400 text-lg">⬇️ 引入局内: {{ assetStore.insertCharData.name }}</h2><button @click="close" class="text-slate-400 hover:text-white text-xl">✕</button></div>
      <div class="p-6 space-y-4">
        <textarea v-model="assetStore.insertCharData.entrance" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none h-28 resize-none shadow-inner" placeholder="描述出场方式..."></textarea>
        <div class="flex justify-end gap-3 mt-4">
          <button @click="close" class="px-4 py-2 bg-slate-800 text-slate-300 rounded font-bold hover:bg-slate-700">取消</button>
          <button class="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded font-bold shadow-lg">发送指令</button>
        </div>
      </div>
    </div>
  </div>
</template>