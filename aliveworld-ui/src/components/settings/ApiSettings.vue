<script setup>
import { configStore } from '../../store/configStore';
</script>

<template>
  <section>
    <h3 class="text-sm font-bold text-emerald-400 mb-3 border-b border-slate-700 pb-2">大语言模型配置（实时生效）</h3>
    <div class="space-y-3">
      <div><label class="text-xs text-slate-400 block mb-1">API Base URL</label><input v-model="configStore.globalSettings.apiBaseUrl" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" /></div>
      <div><label class="text-xs text-slate-400 block mb-1">API Key（密钥）</label><input type="password" v-model="configStore.globalSettings.apiKey" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" /></div>
      <div><label class="text-xs text-slate-400 block mb-1">请求模型（Model）</label><input v-model="configStore.globalSettings.model" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" /></div>
    </div>
  </section>
</template>
