<script setup>
import { uiStore } from '../../store/uiStore';
</script>

<template>
  <Teleport to="body">
    <div
      role="status"
      aria-live="polite"
      class="pointer-events-none fixed left-1/2 top-16 z-[220] flex max-w-[min(90vw,38rem)] -translate-x-1/2 items-center gap-2 rounded-full border px-6 py-3 text-sm font-bold shadow-2xl transition-all duration-300"
      :class="[
        uiStore.toast.show ? 'translate-y-0 opacity-100' : '-translate-y-10 opacity-0',
        uiStore.toast.type === 'error'
          ? 'border-rose-200/80 bg-rose-500 text-white shadow-rose-950/70 ring-2 ring-rose-300/40'
          : 'border-emerald-200/70 bg-emerald-400 text-slate-950 shadow-emerald-950/60 ring-2 ring-emerald-200/30'
      ]"
    >
      <span>{{ uiStore.toast.type === 'error' ? '⚠️' : '✨' }}</span>
      <span>{{ uiStore.toast.message }}</span>
    </div>
  </Teleport>
</template>
