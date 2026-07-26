<script setup>
import { ref } from 'vue';
import { assetStore } from '../../store/assetStore';
import { configStore } from '../../store/configStore';
import { uiStore } from '../../store/uiStore';

const sourceRoot = ref('');
const overwriteConfig = ref(false);
const syncing = ref(false);
const report = ref(null);

const syncLegacyData = async () => {
  syncing.value = true;
  report.value = null;
  try {
    const response = await fetch('/api/v1/lobby/migration/legacy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_root: sourceRoot.value.trim() || null,
        overwrite_config: overwriteConfig.value,
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || '同步旧资产失败');
    report.value = data;
    await Promise.all([assetStore.fetchAssets(), configStore.fetchFromBackend()]);
    uiStore.showToast(`已同步 ${data.copied_files} 个文件`);
  } catch (error) {
    report.value = { status: 'error', message: error.message };
    uiStore.showToast(error.message, 'error');
  } finally {
    syncing.value = false;
  }
};
</script>

<template>
  <section class="space-y-5">
    <div>
      <h3 class="mb-2 border-b border-slate-700 pb-2 text-sm font-bold text-cyan-300">📦 数据与迁移</h3>
      <p class="text-[11px] leading-relaxed text-slate-400">从旧版 AliveWorld 复制个人存档、角色卡、世界书、文风卡、实体、图片与工坊草稿。只复制缺失文件，不删除旧数据，也不覆盖同名资产。</p>
    </div>

    <button @click="syncLegacyData" :disabled="syncing" class="rounded-lg bg-cyan-700 px-4 py-2 text-xs font-bold text-white transition hover:bg-cyan-600 disabled:cursor-wait disabled:opacity-50">{{ syncing ? '正在同步…' : '自动检测并同步旧资产' }}</button>

    <details class="rounded-xl border border-slate-700 bg-slate-900/40 p-3">
      <summary class="cursor-pointer text-xs font-bold text-slate-300">高级：手动指定旧项目目录</summary>
      <label class="mt-3 block">
        <span class="mb-1 block text-xs text-slate-400">旧版 AliveWorld 根目录</span>
        <input v-model="sourceRoot" placeholder="例如 D:\Games\AliveWorld（该目录下应有 data 文件夹）" class="w-full rounded border border-slate-700 bg-slate-950 p-2 text-xs text-slate-200 outline-none focus:border-cyan-600" />
      </label>
      <label class="mt-3 flex items-start gap-2 text-xs text-slate-300">
        <input v-model="overwriteConfig" type="checkbox" class="mt-0.5" />
        <span>同时用旧版 API 配置覆盖当前配置<br><span class="text-[10px] text-amber-400/80">只有明确希望恢复旧密钥、地址和模型时才勾选。</span></span>
      </label>
    </details>

    <div v-if="report?.status === 'success'" class="rounded-lg border border-emerald-800/60 bg-emerald-950/20 p-3 text-xs text-emerald-200">
      <p>同步完成：新增 {{ report.copied_files }} 个文件，跳过 {{ report.skipped_conflicts }} 个同名冲突。</p>
      <p class="mt-1 text-[10px] text-emerald-400/70">API 配置：{{ report.copied_config ? '已同步并立即生效' : '未改动' }}</p>
    </div>
    <div v-else-if="report?.status === 'error'" class="rounded-lg border border-rose-800/60 bg-rose-950/20 p-3 text-xs text-rose-300">{{ report.message }}</div>
  </section>
</template>
