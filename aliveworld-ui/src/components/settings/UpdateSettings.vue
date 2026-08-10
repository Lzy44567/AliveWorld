<script setup>
import { onBeforeUnmount, ref } from 'vue';
import { onboardingStore } from '../../store/onboardingStore';
import { uiStore } from '../../store/uiStore';
import { updateApi } from '../../api/updateApi';

const checking = ref(false);
const result = ref(null);
const error = ref('');
const updateState = ref(null);
const updating = ref(false);
let updatePoll = null;

onBeforeUnmount(() => {
  if (updatePoll) window.clearTimeout(updatePoll);
});

async function checkUpdate() {
  checking.value = true;
  result.value = null;
  error.value = '';
  try {
    result.value = await updateApi.check(true);
    updateState.value = await updateApi.status().catch(() => null);
  } catch (reason) {
    error.value = reason?.message || '暂时无法检查更新；这不会影响游戏。';
  } finally {
    checking.value = false;
  }
}

async function waitForPrepared() {
  try {
    updateState.value = await updateApi.status();
    if (updateState.value.status === 'ready') {
      await updateApi.install();
      updateState.value = { ...updateState.value, status: 'installing', message: '正在重启并安装更新……' };
      return;
    }
    if (updateState.value.status === 'failed') {
      throw new Error(updateState.value.error || updateState.value.message || '更新准备失败。');
    }
    updatePoll = window.setTimeout(waitForPrepared, 500);
  } catch (reason) {
    updating.value = false;
    error.value = reason?.message || '一键更新失败，请稍后重试。';
  }
}

async function startOneClickUpdate() {
  updating.value = true;
  error.value = '';
  try {
    updateState.value = await updateApi.prepare(true);
    await waitForPrepared();
  } catch (reason) {
    updating.value = false;
    error.value = reason?.message || '一键更新失败，请稍后重试。';
  }
}

async function cancelUpdate() {
  if (updatePoll) window.clearTimeout(updatePoll);
  updatePoll = null;
  try {
    updateState.value = await updateApi.cancel();
  } catch (reason) {
    error.value = reason?.message || '取消下载失败。';
  } finally {
    updating.value = false;
  }
}

async function restartGuide() {
  uiStore.modals.settings = false;
  await onboardingStore.restart();
}
</script>

<template>
  <section class="space-y-5">
    <header>
      <h3 class="text-lg font-bold text-cyan-300">ℹ️ 关于与更新</h3>
      <p class="mt-1 text-sm text-slate-400">
        只在你点击按钮时读取 AliveWorld 官方 GitHub Release，不会上传存档、资产、配置或设备信息。
      </p>
    </header>

    <div class="rounded-xl border border-slate-700 bg-slate-900/45 p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p class="text-sm text-slate-400">当前版本</p>
          <p class="font-mono text-base text-slate-100">{{ result?.current_version || '以左上角版本标识为准' }}</p>
        </div>
        <button
          type="button"
          class="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-bold text-white transition hover:bg-cyan-600 disabled:cursor-wait disabled:opacity-60"
          :disabled="checking"
          @click="checkUpdate"
        >
          {{ checking ? '正在检查…' : '检查更新' }}
        </button>
      </div>

      <p v-if="error" class="rounded-lg border border-amber-700/70 bg-amber-950/35 p-3 text-sm text-amber-200">
        {{ error }}
      </p>

      <div v-if="result" class="rounded-lg border p-3" :class="result.update_available ? 'border-emerald-600/70 bg-emerald-950/25' : 'border-slate-700 bg-slate-950/30'">
        <template v-if="result.latest_version">
          <p class="font-bold" :class="result.update_available ? 'text-emerald-300' : 'text-slate-200'">
            {{ result.update_available ? `发现新版本 ${result.latest_version}` : `当前没有更高版本（最新 ${result.latest_version}）` }}
          </p>
          <p v-if="result.prerelease" class="mt-1 text-xs text-amber-300">该版本属于测试版。</p>
          <p v-if="result.title" class="mt-2 text-sm text-slate-300">{{ result.title }}</p>
          <p v-if="result.notes" class="mt-2 max-h-40 overflow-y-auto whitespace-pre-wrap text-xs leading-5 text-slate-400 custom-scrollbar">{{ result.notes }}</p>
        </template>
        <p v-else class="text-sm text-slate-300">{{ result.message }}</p>
        <a
          :href="result.release_url || result.releases_url"
          target="_blank"
          rel="noopener noreferrer"
          class="mt-3 inline-flex rounded-md border border-cyan-700 px-3 py-1.5 text-sm font-bold text-cyan-300 hover:bg-cyan-950/40"
        >
          打开官方发布页
        </a>
        <button
          v-if="result.update_available && updateState?.supported"
          type="button"
          class="ml-2 mt-3 inline-flex rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-bold text-white hover:bg-emerald-600 disabled:cursor-wait disabled:opacity-60"
          :disabled="updating"
          @click="startOneClickUpdate"
        >
          {{ updating ? '正在更新…' : '一键更新并重启' }}
        </button>
        <p v-else-if="result.update_available && updateState && !updateState.supported" class="mt-2 text-xs text-slate-400">
          当前是源码运行模式，请使用 Git 更新或从发布页下载；Windows 便携版才显示一键安装。
        </p>
      </div>

      <div v-if="updating && updateState" class="space-y-2 rounded-lg border border-cyan-800/60 bg-cyan-950/20 p-3">
        <div class="flex items-center justify-between gap-3 text-xs">
          <span class="text-cyan-200">{{ updateState.message }}</span>
          <span class="font-mono text-slate-300">{{ updateState.progress || 0 }}%</span>
        </div>
        <div class="h-2 overflow-hidden rounded-full bg-slate-800">
          <div class="h-full rounded-full bg-gradient-to-r from-cyan-500 to-emerald-400 transition-all" :style="{ width: `${updateState.progress || 0}%` }"></div>
        </div>
        <p class="text-[11px] text-slate-500">下载、校验和暂存均自动完成；安装时 AliveWorld 会退出并由更新助手重新打开。</p>
        <button
          v-if="['downloading', 'verifying', 'cancelling'].includes(updateState.status)"
          type="button"
          class="rounded-md border border-slate-600 px-2.5 py-1 text-xs text-slate-300 hover:bg-slate-800"
          :disabled="updateState.status === 'cancelling'"
          @click="cancelUpdate"
        >
          {{ updateState.status === 'cancelling' ? '正在取消…' : '取消下载' }}
        </button>
      </div>
    </div>

    <div class="rounded-xl border border-indigo-800/60 bg-indigo-950/20 p-4 text-sm leading-6 text-slate-300">
      <p class="font-bold text-indigo-200">当前更新方式</p>
      <p>便携版可使用“一键更新并重启”：自动下载、校验、备份程序、安装并验证新版，整个过程不会替换 <code>UserData</code>。</p>
      <p class="mt-1 text-slate-400">若新版启动失败，独立更新助手会尝试恢复并重新打开旧版。</p>
    </div>

    <div class="rounded-xl border border-emerald-900/60 bg-emerald-950/15 p-4 text-sm leading-6 text-slate-300">
      <p class="font-bold text-emerald-200">快速开始</p>
      <p class="text-slate-400">重新打开首次使用说明和入门故事入口。该操作不会修改现有存档、资产或配置。</p>
      <button type="button" class="mt-3 rounded-lg border border-emerald-700 px-3 py-1.5 text-xs font-bold text-emerald-300 hover:bg-emerald-950/40" @click="restartGuide">重新开始新手引导</button>
    </div>
  </section>
</template>
