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
    <details class="mt-5 rounded-xl border border-fuchsia-900/50 bg-fuchsia-950/10 p-3">
      <summary class="cursor-pointer text-xs font-bold text-fuchsia-300">🪞 偏好分析模型（可选）</summary>
      <p class="mt-2 text-[10px] leading-relaxed text-slate-500">全部留空时继承正文 API。深度分析低频异步运行，不阻塞正文；开启敏感分析后，相关证据会发送给这里配置的服务商。</p>
      <div class="mt-3 space-y-3">
        <div><label class="text-xs text-slate-400 block mb-1">API Base URL</label><input v-model="configStore.globalSettings.preferenceApiBaseUrl" placeholder="留空继承正文 API" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" /></div>
        <div><label class="text-xs text-slate-400 block mb-1">API Key</label><input type="password" v-model="configStore.globalSettings.preferenceApiKey" placeholder="留空继承正文 API Key" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" /></div>
        <div><label class="text-xs text-slate-400 block mb-1">模型</label><input v-model="configStore.globalSettings.preferenceModel" placeholder="留空继承正文模型" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" /></div>
      </div>
    </details>
  </section>
</template>
