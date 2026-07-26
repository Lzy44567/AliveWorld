<script setup>
import { ref } from 'vue';
import { configStore } from '../../store/configStore';
import { uiStore } from '../../store/uiStore';
import MemorySettings from './MemorySettings.vue';
import SecretField from './SecretField.vue';

const testing = ref(false);
const testResult = ref(null);

const saveAndTest = async () => {
  testing.value = true;
  testResult.value = null;
  try {
    await configStore.syncToBackend();
    const response = await fetch('/api/v1/game/system_config/test', { method: 'POST' });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || '模型测试失败');
    testResult.value = data;
    uiStore.showToast(`${data.message}：${data.model}`);
  } catch (error) {
    testResult.value = { connected: false, message: error.message };
    uiStore.showToast(error.message, 'error');
  } finally {
    testing.value = false;
  }
};
</script>

<template>
  <section>
    <h3 class="text-sm font-bold text-emerald-400 mb-3 border-b border-slate-700 pb-2">大语言模型配置（实时生效）</h3>
    <div class="space-y-3">
      <div><label class="text-xs text-slate-400 block mb-1">API Base URL</label><input v-model="configStore.globalSettings.apiBaseUrl" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" /></div>
      <SecretField v-model="configStore.globalSettings.apiKey" :configured="configStore.globalSettings.apiKeyConfigured" field="apiKey" label="API Key（密钥）" />
      <div><label class="text-xs text-slate-400 block mb-1">请求模型（Model）</label><input v-model="configStore.globalSettings.model" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" /></div>
      <div class="flex flex-wrap items-center gap-3 pt-1">
        <button @click="saveAndTest" :disabled="testing" class="rounded-lg bg-emerald-700 px-4 py-2 text-xs font-bold text-white transition hover:bg-emerald-600 disabled:cursor-wait disabled:opacity-50">{{ testing ? '正在请求模型…' : '保存并测试连接' }}</button>
        <span v-if="testResult" class="text-xs" :class="testResult.connected ? 'text-emerald-400' : 'text-rose-400'">{{ testResult.message }}</span>
      </div>
      <p class="text-[10px] leading-relaxed text-slate-500">测试会真实发送一条极短请求，可能产生极少量 Token 费用。DeepSeek 官方接口当前模型名为 deepseek-v4-flash 或 deepseek-v4-pro。</p>
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
