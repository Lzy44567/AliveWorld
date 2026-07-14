<script setup>
import { onMounted, ref } from 'vue';
import { configStore } from '../../store/configStore';
import { gameStore } from '../../store/gameStore';
import { uiStore } from '../../store/uiStore';
import { imageApi } from '../../api/imageApi';
import { imageStore } from '../../store/imageStore';

const checking = ref(false);
const testing = ref(false);
const connection = ref(null);
const checkpoints = ref([]);
const workflows = ref([]);

const loadWorkflows = async () => {
  try { workflows.value = await imageApi.listWorkflows(); }
  catch (error) { uiStore.showToast(error.message, 'error'); }
};

const checkConnection = async () => {
  checking.value = true;
  connection.value = null;
  try {
    connection.value = await imageApi.checkComfyUI(configStore.globalSettings.imageApiUrl);
    checkpoints.value = connection.value.checkpoints || [];
    if (connection.value.connected) uiStore.showToast('ComfyUI 连接正常');
    else uiStore.showToast(connection.value.message || 'ComfyUI 无法连接', 'error');
  } catch (error) { uiStore.showToast(error.message, 'error'); }
  finally { checking.value = false; }
};

const generateTest = async () => {
  if (!gameStore.sessionId) return uiStore.showToast('请先创建或载入一个存档', 'error');
  if (!configStore.globalSettings.imageCheckpoint) return uiStore.showToast('请先选择 checkpoint', 'error');
  testing.value = true;
  try {
    const task = await imageApi.testComfyUI(gameStore.sessionId, {
      baseUrl: configStore.globalSettings.imageApiUrl,
      checkpoint: configStore.globalSettings.imageCheckpoint,
      workflowId: configStore.globalSettings.imageWorkflowId
    });
    imageStore.upsert(task);
    imageStore.sessionId = gameStore.sessionId;
    imageStore.syncPolling();
    uiStore.showToast('测试图已进入后台队列');
  } catch (error) { uiStore.showToast(error.message, 'error'); }
  finally { testing.value = false; }
};

onMounted(loadWorkflows);
</script>

<template>
  <section class="space-y-5">
    <div>
      <h3 class="text-sm font-bold text-fuchsia-300 mb-2 border-b border-slate-700 pb-2">🎨 本地 ComfyUI</h3>
      <p class="text-[11px] text-slate-400 leading-relaxed">AliveWorld 不会安装或启动 ComfyUI。请先自行启动 ComfyUI，再检查连接。默认地址通常为 http://127.0.0.1:8188。</p>
    </div>
    <label class="block"><span class="field-label">ComfyUI 地址</span><input v-model="configStore.globalSettings.imageApiUrl" class="field-input" /></label>
    <div class="flex gap-2">
      <button @click="checkConnection" :disabled="checking" class="action secondary">{{ checking ? '检查中…' : '检查连接与模型' }}</button>
      <span v-if="connection" class="self-center text-xs" :class="connection.connected ? 'text-emerald-400' : 'text-rose-400'">{{ connection.message }}</span>
    </div>
    <label class="block"><span class="field-label">Checkpoint</span>
      <select v-model="configStore.globalSettings.imageCheckpoint" class="field-input">
        <option value="">请先检查连接并选择模型</option>
        <option v-for="item in checkpoints" :key="item" :value="item">{{ item }}</option>
      </select>
    </label>
    <label class="block"><span class="field-label">工作流</span>
      <select v-model="configStore.globalSettings.imageWorkflowId" class="field-input">
        <option v-for="item in workflows" :key="item.id" :value="item.id">{{ item.name }}{{ item.is_template ? '（内置）' : '' }}</option>
      </select>
    </label>
    <label class="block"><span class="field-label">默认负面提示词</span><textarea v-model="configStore.globalSettings.imageNegativePrompt" rows="3" class="field-input resize-y" /></label>
    <label class="block"><span class="field-label">画风偏好提示（可空）</span><textarea v-model="configStore.globalSettings.imageStylePreference" rows="2" class="field-input resize-y" placeholder="例如：柔和厚涂、电影光影……" /></label>
    <label class="block"><span class="field-label">画面表现尺度（可空）</span><input v-model="configStore.globalSettings.imagePresentationLevel" class="field-input" placeholder="例如：唯美、若隐若现、露点……" /></label>
    <div class="rounded-lg border border-amber-800/60 bg-amber-950/20 p-3 text-[11px] text-amber-200/80">
      测试图会真实占用显卡并生成一张 512×512 白底红色圆形；它不调用大语言模型。
    </div>
    <button @click="generateTest" :disabled="testing" class="action primary">{{ testing ? '已提交，请等待…' : '生成极简测试图' }}</button>
  </section>
</template>

<style scoped>
.field-label { display:block; margin-bottom:.35rem; color:rgb(148 163 184); font-size:.75rem; }
.field-input { width:100%; border:1px solid rgb(51 65 85); border-radius:.5rem; background:rgb(15 23 42); padding:.6rem .7rem; color:rgb(226 232 240); font-size:.8rem; outline:none; }
.field-input:focus { border-color:rgb(217 70 239); }
.action { border-radius:.5rem; padding:.55rem .9rem; font-size:.75rem; font-weight:700; transition:.15s; }
.action:disabled { opacity:.5; cursor:not-allowed; }
.primary { background:rgb(192 38 211); color:white; }
.primary:hover:not(:disabled) { background:rgb(217 70 239); }
.secondary { background:rgb(51 65 85); color:rgb(226 232 240); }
.secondary:hover:not(:disabled) { background:rgb(71 85 105); }
</style>
