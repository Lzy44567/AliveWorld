<script setup>
import { configStore } from '../../store/configStore';
import MemorySettings from './MemorySettings.vue';
import SecretField from './SecretField.vue';
</script>

<template>
  <section>
    <h3 class="text-sm font-bold text-emerald-400 mb-3 border-b border-slate-700 pb-2">大语言模型配置（实时生效）</h3>
    <div class="space-y-3">
      <div><label class="text-xs text-slate-400 block mb-1">API Base URL</label><input v-model="configStore.globalSettings.apiBaseUrl" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" /></div>
      <SecretField v-model="configStore.globalSettings.apiKey" :configured="configStore.globalSettings.apiKeyConfigured" field="apiKey" label="API Key（密钥）" />
      <div><label class="text-xs text-slate-400 block mb-1">请求模型（Model）</label><input v-model="configStore.globalSettings.model" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" /></div>
    </div>
    <details class="mt-5 rounded-xl border border-fuchsia-900/50 bg-fuchsia-950/10 p-3">
      <summary class="cursor-pointer text-xs font-bold text-fuchsia-300">🪞 偏好分析模型（可选）</summary>
      <p class="mt-2 text-[10px] leading-relaxed text-slate-500">全部留空时继承正文 API。深度分析低频异步运行，不阻塞正文；开启敏感分析后，相关证据会发送给这里配置的服务商。</p>
      <div class="mt-3 space-y-3">
        <div><label class="text-xs text-slate-400 block mb-1">API Base URL</label><input v-model="configStore.globalSettings.preferenceApiBaseUrl" placeholder="留空继承正文 API" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" /></div>
        <SecretField v-model="configStore.globalSettings.preferenceApiKey" :configured="configStore.globalSettings.preferenceApiKeyConfigured" field="preferenceApiKey" label="API Key" placeholder="留空继承正文 API Key" empty-status="未单独配置，将继承正文 API Key" />
        <div><label class="text-xs text-slate-400 block mb-1">模型</label><input v-model="configStore.globalSettings.preferenceModel" placeholder="留空继承正文模型" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" /></div>
      </div>
    </details>
    <details class="mt-4 rounded-xl border border-indigo-900/60 bg-indigo-950/15 p-3">
      <summary class="cursor-pointer text-xs font-bold text-indigo-300">🧠 记忆压缩模型（可选）</summary>
      <p class="mt-2 text-[10px] leading-relaxed text-slate-500">故事记忆压缩属于模型接口配置。默认继承正文 API；只有需要独立低成本模型时才展开填写。</p>
      <div class="mt-3"><MemorySettings /></div>
    </details>
  </section>
</template>
