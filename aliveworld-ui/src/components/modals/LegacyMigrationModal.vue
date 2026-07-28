<script setup>
import { ref } from 'vue';
import { assetStore } from '../../store/assetStore';
import { configStore } from '../../store/configStore';
import { uiStore } from '../../store/uiStore';
import { onboardingStore } from '../../store/onboardingStore';

const syncing = ref(false);
const errorMessage = ref('');

const close = () => {
  uiStore.modals.legacyMigration = false;
  window.setTimeout(() => onboardingStore.offerStory(), 0);
};

const syncNow = async () => {
  syncing.value = true;
  errorMessage.value = '';
  try {
    const response = await fetch('/api/v1/lobby/migration/legacy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_root: uiStore.legacyMigrationSource || null,
        overwrite_config: false,
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || '同步旧资产失败');
    await Promise.all([assetStore.fetchAssets(), configStore.fetchFromBackend()]);
    uiStore.showToast(`旧资产同步完成：新增 ${data.copied_files} 个文件`);
    close();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    syncing.value = false;
  }
};
</script>

<template>
  <div class="fixed inset-0 z-[70] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
    <div class="w-full max-w-lg overflow-hidden rounded-2xl border border-cyan-700/70 bg-slate-900 shadow-2xl">
      <div class="border-b border-slate-700 bg-slate-950/70 px-6 py-5">
        <h2 class="text-lg font-bold text-cyan-200">📦 检测到旧版 AliveWorld 资产</h2>
        <p class="mt-1 text-xs text-slate-400">可以把旧存档和个人资产复制到当前便携版。</p>
      </div>
      <div class="space-y-4 p-6">
        <div class="rounded-lg border border-slate-700 bg-slate-950/70 p-3 font-mono text-[11px] text-slate-300">{{ uiStore.legacyMigrationSource }}</div>
        <p class="text-xs leading-relaxed text-slate-300">将复制旧存档、角色卡、世界书、文风、实体、图片和工坊草稿。旧文件不会被移动或删除，当前已有的同名文件不会被覆盖。</p>
        <p class="rounded-lg border border-amber-900/60 bg-amber-950/20 p-3 text-[11px] leading-relaxed text-amber-200/80">现在取消不会丢失任何内容；之后仍可前往“设置 → 数据与迁移”手动同步。只要尚未完成同步，下次启动时仍会提醒。</p>
        <p v-if="errorMessage" class="rounded-lg border border-rose-800/70 bg-rose-950/30 p-3 text-xs text-rose-300">{{ errorMessage }}</p>
      </div>
      <div class="flex justify-end gap-3 border-t border-slate-700 bg-slate-950/40 px-6 py-4">
        <button @click="close" :disabled="syncing" class="rounded-lg bg-slate-700 px-4 py-2 text-xs font-bold text-slate-200 hover:bg-slate-600 disabled:opacity-50">暂不同步</button>
        <button @click="syncNow" :disabled="syncing" class="rounded-lg bg-cyan-700 px-4 py-2 text-xs font-bold text-white hover:bg-cyan-600 disabled:cursor-wait disabled:opacity-50">{{ syncing ? '正在同步…' : '同步旧资产' }}</button>
      </div>
    </div>
  </div>
</template>
