<script setup>
defineProps({ text: { type: String, required: true } });
</script>
<template><span class="group relative ml-1 inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full border border-slate-500 text-[9px] text-slate-400" tabindex="0">?<span class="pointer-events-none absolute bottom-full left-1/2 z-30 mb-2 hidden w-64 -translate-x-1/2 rounded-lg border border-slate-700 bg-slate-950 p-2 text-left text-[10px] font-normal leading-relaxed text-slate-300 shadow-xl group-hover:block group-focus:block">{{ text }}</span></span></template>
