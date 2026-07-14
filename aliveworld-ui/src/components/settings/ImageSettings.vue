<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { configStore } from '../../store/configStore';
import { uiStore } from '../../store/uiStore';
import { imageApi } from '../../api/imageApi';

const checking = ref(false);
const testing = ref(false);
const connection = ref(null);
const checkpoints = ref([...(configStore.globalSettings.imageCheckpoints || [])]);
const workflows = ref([]);
const importing = ref(false);
const latestTest = ref(null);
let testPollHandle = null;
const currentModelProfile = computed({
  get: () => configStore.globalSettings.imageModelProfiles?.[configStore.globalSettings.imageCheckpoint] || '',
  set: value => {
    configStore.globalSettings.imageModelProfiles = {
      ...(configStore.globalSettings.imageModelProfiles || {}),
      [configStore.globalSettings.imageCheckpoint]: value
    };
  }
});
const testStatusText = { ready:'准备提交', submitted:'已提交', running:'生成中', succeeded:'测试成功', failed:'测试失败', cancelled:'已取消' };

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
    configStore.globalSettings.imageCheckpoints = checkpoints.value;
    if (connection.value.connected) uiStore.showToast('ComfyUI 连接正常');
    else uiStore.showToast(connection.value.message || 'ComfyUI 无法连接', 'error');
  } catch (error) { uiStore.showToast(error.message, 'error'); }
  finally { checking.value = false; }
};

const generateTest = async () => {
  if (!configStore.globalSettings.imageCheckpoint) return uiStore.showToast('请先选择生图模型', 'error');
  testing.value = true;
  try {
    const task = await imageApi.testComfyUI({
      baseUrl: configStore.globalSettings.imageApiUrl,
      checkpoint: configStore.globalSettings.imageCheckpoint,
      workflowId: configStore.globalSettings.imageWorkflowId
    });
    latestTest.value = task;
    startTestPolling(task);
    uiStore.showToast('测试图已进入后台队列');
  } catch (error) { uiStore.showToast(error.message, 'error'); }
  finally { testing.value = false; }
};

const startTestPolling = task => {
  if (testPollHandle) window.clearInterval(testPollHandle);
  if (['succeeded','failed','cancelled'].includes(task.status)) return;
  testPollHandle = window.setInterval(async () => {
    try {
      latestTest.value = await imageApi.getLibraryTask('global', task.id);
      if (['succeeded','failed','cancelled'].includes(latestTest.value.status)) {
        window.clearInterval(testPollHandle); testPollHandle = null;
        uiStore.showToast(latestTest.value.status === 'succeeded' ? '测试图片已生成' : `测试失败：${latestTest.value.error_message || '未知错误'}`, latestTest.value.status === 'succeeded' ? 'success' : 'error');
      }
    } catch (_) { /* 下次轮询重试 */ }
  }, 1500);
};

const importWorkflow = async (event) => {
  const file = event.target.files?.[0];
  event.target.value = '';
  if (!file) return;
  importing.value = true;
  try {
    const parsed = JSON.parse(await file.text());
    const stem = file.name.replace(/\.json$/i, '').replace(/[^A-Za-z0-9_-]+/g, '_') || 'imported_workflow';
    const payload = parsed.workflow
      ? { ...parsed, id: parsed.id || stem, name: parsed.name || file.name }
      : { id: stem, name: file.name, workflow: parsed };
    const saved = await imageApi.importWorkflow(payload);
    await loadWorkflows();
    configStore.globalSettings.imageWorkflowId = saved.id;
    uiStore.showToast(`工作流“${saved.name}”已导入`);
  } catch (error) { uiStore.showToast(`导入失败：${error.message}`, 'error'); }
  finally { importing.value = false; }
};

onMounted(async () => {
  await loadWorkflows();
  try {
    const library = await imageApi.listLibrary();
    latestTest.value = library.find(task => task.scope_id === 'global' && task.context_snapshot?.test_task) || null;
    if (latestTest.value) startTestPolling(latestTest.value);
  } catch (_) { /* 后端未启动时保持降级 */ }
  if (!checkpoints.value.length) checkConnection();
});
onBeforeUnmount(() => { if (testPollHandle) window.clearInterval(testPollHandle); });
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
    <label class="block"><span class="field-label">生图模型 <span class="text-slate-600">（ComfyUI Checkpoint 文件）</span></span>
      <select v-model="configStore.globalSettings.imageCheckpoint" class="field-input">
        <option value="">正在读取或尚未选择模型</option>
        <option v-if="configStore.globalSettings.imageCheckpoint && !checkpoints.includes(configStore.globalSettings.imageCheckpoint)" :value="configStore.globalSettings.imageCheckpoint">{{ configStore.globalSettings.imageCheckpoint }}（上次选择）</option>
        <option v-for="item in checkpoints" :key="item" :value="item">{{ item }}</option>
      </select>
    </label>
    <label v-if="configStore.globalSettings.imageCheckpoint" class="block"><span class="field-label">当前模型特性说明（可选）</span><textarea v-model="currentModelProfile" rows="2" class="field-input resize-y" placeholder="例如：偏好 Danbooru 英文标签、适合动漫人物、推荐的起始标签……" /></label>
    <p class="-mt-3 text-[10px] text-slate-500">AliveWorld 会把模型文件名和这段说明交给提示词 AI；不会仅凭文件名猜测模型能力。</p>
    <label class="block"><span class="field-label">工作流</span>
      <select v-model="configStore.globalSettings.imageWorkflowId" class="field-input">
        <option v-for="item in workflows" :key="item.id" :value="item.id">{{ item.name }}{{ item.is_template ? '（内置）' : '' }}</option>
      </select>
    </label>
    <label class="action secondary inline-block cursor-pointer">{{ importing ? '导入中…' : '导入 ComfyUI API 工作流 JSON' }}<input type="file" accept="application/json,.json" class="hidden" :disabled="importing" @change="importWorkflow" /></label>
    <p class="text-[10px] text-slate-500">会自动识别常见核心节点。多个同类节点或正负提示标题不明确时会拒绝导入，不会猜测运行。</p>
    <label class="block"><span class="field-label">默认负面提示词</span><textarea v-model="configStore.globalSettings.imageNegativePrompt" rows="3" class="field-input resize-y" /></label>
    <label class="block"><span class="field-label">画风偏好提示（可空）</span><textarea v-model="configStore.globalSettings.imageStylePreference" rows="2" class="field-input resize-y" placeholder="例如：柔和厚涂、电影光影……" /></label>
    <label class="block"><span class="field-label">画面表现尺度（可空）</span><input v-model="configStore.globalSettings.imagePresentationLevel" class="field-input" placeholder="例如：唯美、若隐若现、露点……" /></label>
    <div class="rounded-lg border border-amber-800/60 bg-amber-950/20 p-3 text-[11px] text-amber-200/80">
      测试图会真实占用显卡并生成一张 512×512 的“窗边蓝色蝴蝶结白猫”；它不调用大语言模型，也不代表默认画风。
    </div>
    <button @click="generateTest" :disabled="testing" class="action primary">{{ testing ? '已提交，请等待…' : '生成极简测试图' }}</button>
    <div v-if="latestTest" class="rounded-lg border border-fuchsia-900/60 bg-slate-950/70 p-3">
      <div class="flex justify-between text-xs"><span class="text-fuchsia-300">{{ testStatusText[latestTest.status] || latestTest.status }}</span><span class="font-mono text-[9px] text-slate-600">{{ latestTest.id }}</span></div>
      <div v-if="['ready','submitted','running'].includes(latestTest.status)" class="mt-2"><div class="h-1.5 overflow-hidden rounded bg-slate-800"><div class="h-full w-1/3 animate-pulse bg-fuchsia-500" /></div><p class="mt-1 text-[9px] text-slate-600">运行状态动画，不代表精确百分比。</p></div>
      <p v-if="latestTest.status==='failed'" class="mt-2 text-xs text-rose-300">{{ latestTest.error_message || 'ComfyUI 执行失败' }}</p>
      <img v-if="latestTest.status==='succeeded' && latestTest.output_images?.[0]" :src="imageApi.absoluteImageUrl(latestTest.output_images[0])" class="mt-3 max-h-64 rounded border border-slate-700 bg-black object-contain" />
    </div>
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
