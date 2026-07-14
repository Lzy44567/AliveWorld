<!-- src/components/modals/GalleryModal.vue -->
<script setup>
import { computed, onMounted, ref } from 'vue';
import { uiStore } from '../../store/uiStore';
import { gameStore } from '../../store/gameStore';
import { imageStore } from '../../store/imageStore';
import { imageApi } from '../../api/imageApi';
const close = () => { uiStore.modals.gallery = false; };
const filter = ref('all');
const selectedUrl = ref('');
const completed = computed(() => imageStore.tasks.filter(task => task.status === 'succeeded' && task.output_images?.length && (filter.value === 'all' || task.intent === filter.value)));
onMounted(() => { if (gameStore.sessionId) imageStore.load(gameStore.sessionId).catch(() => {}); });
</script>
<template>
  <div class="fixed inset-0 bg-black/80 z-[70] flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-aw_panel border border-slate-600 rounded-xl w-full max-w-5xl shadow-2xl flex flex-col slide-up overflow-hidden h-[80vh]">
      <div class="p-4 border-b border-slate-700 flex justify-between bg-slate-900/80">
        <div><h2 class="font-bold text-amber-400 text-lg flex items-center gap-2">🖼️ {{ gameStore.currentSaveName || '本局' }} · 回忆画廊</h2><p class="text-[10px] text-slate-500">只显示当前故事生成并成功保存的图片</p></div><button @click="close" class="text-slate-400 hover:text-white text-xl">✕</button>
      </div>
      <div class="border-b border-slate-800 px-6 py-3 flex gap-2"><button v-for="item in [{id:'all',name:'全部'},{id:'character_portrait',name:'角色立绘'},{id:'character_cg',name:'角色 CG'},{id:'scene_cg',name:'场景 CG'}]" :key="item.id" @click="filter=item.id" class="rounded-full border px-3 py-1 text-xs" :class="filter===item.id?'border-amber-500 bg-amber-950/50 text-amber-300':'border-slate-700 text-slate-400'">{{ item.name }}</button></div>
      <div class="flex-1 p-6 overflow-y-auto bg-slate-900/30 custom-scrollbar">
        <div v-if="!completed.length" class="h-full flex items-center justify-center text-sm text-slate-500">本局还没有符合条件的生成图片</div>
        <div v-else class="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div v-for="task in completed" :key="task.id" class="bg-slate-900 rounded-lg border border-slate-700 overflow-hidden group relative">
            <img :src="imageApi.absoluteImageUrl(task.output_images[0])" @click="selectedUrl=imageApi.absoluteImageUrl(task.output_images[0])" class="aspect-square w-full object-cover cursor-zoom-in opacity-85 group-hover:opacity-100 transition">
            <div class="p-2"><div class="text-[10px] text-amber-300">{{ {character_portrait:'角色立绘',character_cg:'角色 CG',scene_cg:'场景 CG'}[task.intent] }}</div><div class="mt-1 truncate text-[9px] text-slate-500">{{ task.character_ids?.join('、') || task.context_snapshot?.story_text || task.id }}</div></div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="selectedUrl" @click="selectedUrl=''" class="fixed inset-0 z-[90] flex items-center justify-center bg-black/90 p-8 cursor-zoom-out"><img :src="selectedUrl" class="max-h-full max-w-full object-contain rounded-lg" /></div>
  </div>
</template>
