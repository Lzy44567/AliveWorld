<script setup>
import { uiStore } from '../../store/uiStore';
import CausalLedgerPanel from '../panels/CausalLedgerPanel.vue';
</script>

<template>
  <div class="fixed inset-0 z-[95] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
    <section class="flex h-[88vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-fuchsia-800/70 bg-slate-950 shadow-2xl">
      <header class="flex shrink-0 items-center justify-between border-b border-slate-800 px-5 py-3"><div><h2 class="font-bold text-fuchsia-300">🧾 暗流因果账本</h2><p class="text-[10px] text-slate-500">仅显示并编辑当前故事的幕后影响；默认属于调试功能</p></div><button @click="uiStore.modals.causalLedger=false" class="text-xl text-slate-400 hover:text-white">✕</button></header>
      <CausalLedgerPanel :initial-source="uiStore.ledgerSourceFilter" class="min-h-0 flex-1 p-4" />
    </section>
  </div>
</template>
