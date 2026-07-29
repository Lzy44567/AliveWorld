<script setup>
import { computed, reactive, watch } from 'vue';
import FieldHelp from '../../common/FieldHelp.vue';
import { connectionStore } from '../../../store/connectionStore';
import { configStore } from '../../../store/configStore';
import { uiStore } from '../../../store/uiStore';

const localRoutes = reactive({});
const textProfiles = computed(() => connectionStore.profiles.filter(item => item.category === 'text'));
const tasks = computed(() => Object.entries(connectionStore.routes)
  .filter(([task, route]) => route.category === 'text' && task !== 'story'));

watch(
  () => connectionStore.routes,
  routes => {
    for (const [task, route] of Object.entries(routes || {})) {
      localRoutes[task] = {
        selection: route.connection_id || 'inherit',
        inheritFrom: route.inherit_from || 'story',
        modelOverride: route.model_override || '',
      };
    }
  },
  { immediate: true, deep: true },
);

async function save(task) {
  const route = localRoutes[task];
  try {
    await connectionStore.setRoute(task, route.selection === 'inherit'
      ? { connectionId: '', inheritFrom: route.inheritFrom || 'story', modelOverride: route.modelOverride }
      : { connectionId: route.selection, inheritFrom: '', modelOverride: route.modelOverride });
    uiStore.showToast(`${connectionStore.routes[task]?.label || '功能'}接口已更新`);
  } catch (error) {
    uiStore.showToast(error.message, 'error');
    await connectionStore.refresh();
  }
}

async function saveMemoryLimit() {
  try {
    await configStore.syncToBackend();
    uiStore.showToast('记忆上下文上限已保存');
  } catch (error) {
    uiStore.showToast(error.message, 'error');
  }
}
</script>

<template>
  <details class="mt-5 rounded-xl border border-indigo-900/60 bg-indigo-950/15 p-3">
    <summary class="cursor-pointer text-xs font-bold text-indigo-300">高级功能分配</summary>
    <p class="mt-2 text-[10px] leading-relaxed text-slate-500">默认全部继承主文本接口。只有希望记忆、工坊或偏好分析使用不同服务/模型时才修改；每行会单独自动保存。</p>
    <div class="mt-3 space-y-2">
      <div v-for="[task, routeInfo] in tasks" :key="task" class="rounded-lg border border-slate-700 bg-slate-900/70 p-3">
        <div class="mb-2 flex items-center text-xs font-bold text-slate-300">
          {{ routeInfo.label }}
          <FieldHelp :text="`${routeInfo.label}调用模型时使用的接口。选择继承可减少重复配置；模型覆盖只改变模型名，不复制密钥。`" />
        </div>
        <div class="grid gap-2 md:grid-cols-[1fr_1fr_auto]">
          <select v-model="localRoutes[task].selection" class="route-field" @change="save(task)">
            <option value="inherit">继承主文本接口</option>
            <option v-for="profile in textProfiles" :key="profile.id" :value="profile.id">{{ profile.name }}{{ profile.enabled?'':'（已停用）' }}</option>
          </select>
          <input v-model="localRoutes[task].modelOverride" class="route-field" placeholder="模型覆盖（可空）" @change="save(task)">
          <button class="rounded-lg bg-slate-700 px-3 py-2 text-[10px] text-slate-200" @click="save(task)">应用</button>
        </div>
      </div>
      <div class="rounded-lg border border-slate-700 bg-slate-900/70 p-3">
        <div class="mb-2 flex items-center text-xs font-bold text-slate-300">记忆模型上下文上限<FieldHelp text="用于计算记忆压缩水位，不等于每次都发送这么多 Token。请填写所选记忆模型真实支持的上下文上限。" /></div>
        <input v-model.number="configStore.globalSettings.memoryContextLimit" type="number" min="8192" step="1024" class="route-field w-full" @change="saveMemoryLimit">
      </div>
    </div>
  </details>
</template>

<style scoped>
.route-field {
  @apply min-w-0 rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-2 text-xs text-slate-200 outline-none focus:border-indigo-500;
}
</style>
