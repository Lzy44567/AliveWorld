<script setup>
import { computed } from 'vue';
import { configStore } from '../../store/configStore';

const inheritsMain = computed(() => !configStore.globalSettings.memoryApiKey && !configStore.globalSettings.memoryApiBaseUrl && !configStore.globalSettings.memoryModel);
</script>

<template>
  <section class="space-y-4">
    <div>
      <h3 class="text-sm font-bold text-indigo-300 border-b border-slate-700 pb-2">故事记忆压缩模型</h3>
      <p class="mt-2 text-[11px] leading-relaxed text-slate-500">三个模型字段全部留空时继承正文 API。填写独立地址但留空密钥时使用本地接口占位密钥，不会把正文密钥发送给本地服务。压缩只在达到水位时调用。</p>
    </div>
    <div v-if="inheritsMain" class="rounded-lg border border-indigo-500/30 bg-indigo-950/20 px-3 py-2 text-xs text-indigo-200">当前继承正文模型</div>
    <label class="block"><span class="field-label">压缩 API Base URL（可空）</span><input v-model="configStore.globalSettings.memoryApiBaseUrl" class="field-input" placeholder="留空继承正文 API" /></label>
    <label class="block"><span class="field-label">压缩 API Key（可空）</span><input type="password" v-model="configStore.globalSettings.memoryApiKey" class="field-input" placeholder="留空继承正文 API" /></label>
    <label class="block"><span class="field-label">压缩模型（可空）</span><input v-model="configStore.globalSettings.memoryModel" class="field-input" placeholder="留空继承正文模型" /></label>
    <label class="block">
      <span class="field-label">模型上下文上限</span>
      <input type="number" min="8192" step="1024" v-model.number="configStore.globalSettings.memoryContextLimit" class="field-input" />
      <span class="mt-1 block text-[10px] text-slate-500">系统据此动态计算故事历史高低水位；这不是每次固定切片长度。</span>
    </label>
  </section>
</template>

<style scoped>
.field-label { display: block; margin-bottom: .3rem; font-size: .7rem; color: rgb(148 163 184); }
.field-input { width: 100%; border: 1px solid rgb(51 65 85); border-radius: .5rem; background: rgb(15 23 42); padding: .65rem .75rem; color: rgb(226 232 240); outline: none; }
.field-input:focus { border-color: rgb(99 102 241); }
</style>
