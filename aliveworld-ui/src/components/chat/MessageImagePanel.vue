<script setup>
import { computed, reactive, ref } from 'vue';
import { configStore } from '../../store/configStore';
import { gameStore } from '../../store/gameStore';
import { imageStore } from '../../store/imageStore';
import { uiStore } from '../../store/uiStore';
import { fileToDataUrl, imageApi } from '../../api/imageApi';
import ImageGenerationOptions from '../image/ImageGenerationOptions.vue';

const props = defineProps({ message: { type: Object, required: true } });
const tasks = computed(() => imageStore.forMessage(props.message.id));
const showForm = ref(false);
const prompt = ref('');
const intent = ref('scene_cg');
const submitting = ref(false);
const referenceFiles = ref([]);
const referenceRole = ref('character');
const selectedUrl = ref('');
const deleteConfirmId = ref('');
const options = reactive({
  width: configStore.globalSettings.imageWidth || 768,
  height: configStore.globalSettings.imageHeight || 768,
  count: configStore.globalSettings.imageCount || 1,
  steps: configStore.globalSettings.imageSteps || 20,
  cfg: configStore.globalSettings.imageCfg || 7,
});
const statusText = { queued:'等待提示词', compiling_prompt:'AI 正在整理画面', ready:'准备提交', submitted:'已提交', running:'生成中', succeeded:'已完成', failed:'生成失败', cancelled:'已取消' };
const chooseReferences = event => { referenceFiles.value = [...(event.target.files || [])]; };

const uploadReferences = async () => {
  const references = [];
  for (const file of referenceFiles.value) {
    const uploaded = await imageApi.uploadReference(gameStore.sessionId, { filename:file.name, role:referenceRole.value, data_url:await fileToDataUrl(file) });
    references.push({ path:uploaded.id, role:uploaded.role, label:uploaded.filename });
  }
  return references;
};

const baseTask = async (positive = '') => {
  const settings = configStore.globalSettings;
  if (!settings.imageCheckpoint) throw new Error('请先在“设置 → 生图配置”选择生图模型');
  Object.assign(settings, { imageWidth:options.width, imageHeight:options.height, imageCount:options.count, imageSteps:options.steps, imageCfg:options.cfg });
  return {
    intent:intent.value, source_message_id:props.message.id, provider_id:'comfyui', workflow_id:settings.imageWorkflowId,
    prompt:{ positive, negative:settings.imageNegativePrompt, style_preference:settings.imageStylePreference, presentation_level:settings.imagePresentationLevel, ...options, references:await uploadReferences() },
    context_snapshot:{ story_text:props.message.content }, provider_options:{ base_url:settings.imageApiUrl, checkpoint:settings.imageCheckpoint }
  };
};

const generateWithAI = async () => {
  submitting.value = true;
  try {
    const settings = configStore.globalSettings;
    const task = await baseTask();
    await imageStore.compileAndCreate(gameStore.sessionId, task, {
      intent:intent.value, user_request:prompt.value, source_message_id:props.message.id,
      style_preference:settings.imageStylePreference, presentation_level:settings.imagePresentationLevel,
      model_name:settings.imageCheckpoint, model_profile:settings.imageModelProfiles?.[settings.imageCheckpoint] || ''
    });
    showForm.value = false; prompt.value = ''; referenceFiles.value = [];
    uiStore.showToast('AI 正在后台整理提示词，完成后会自动生图；你可以继续游玩');
  } catch (error) { uiStore.showToast(error.message, 'error'); }
  finally { submitting.value = false; }
};

const generateDirect = async () => {
  if (!prompt.value.trim()) return uiStore.showToast('直接生成模式需要填写生图提示词', 'error');
  submitting.value = true;
  try {
    await imageStore.create(gameStore.sessionId, await baseTask(prompt.value.trim()));
    showForm.value = false; prompt.value = ''; referenceFiles.value = [];
    uiStore.showToast('生图任务已进入后台队列');
  } catch (error) { uiStore.showToast(error.message, 'error'); }
  finally { submitting.value = false; }
};

const regenerate = async task => {
  try { await imageStore.regenerate(task.id); uiStore.showToast('已创建新的重生成任务'); }
  catch (error) { uiStore.showToast(error.message, 'error'); }
};
const removeTask = async task => {
  try { await imageStore.remove(task.id); deleteConfirmId.value = ''; uiStore.showToast('图片与任务记录已删除'); }
  catch (error) { uiStore.showToast(error.message, 'error'); }
};
</script>

<template>
  <div class="mt-2">
    <button v-if="!showForm" @click="showForm=true" class="rounded border border-fuchsia-800/60 bg-fuchsia-950/20 px-2 py-1 text-[11px] text-fuchsia-300 hover:text-fuchsia-200">🎨 生成此处 CG</button>
    <div v-else class="space-y-3 rounded-xl border border-fuchsia-800/60 bg-slate-950/90 p-3">
      <div class="flex gap-2"><select v-model="intent" class="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"><option value="scene_cg">场景 CG</option><option value="character_cg">角色 CG</option></select><span class="self-center text-[10px] text-slate-500">留空也可一键生成；AI 会结合对应正文整理提示词</span></div>
      <textarea v-model="prompt" rows="3" class="w-full resize-y rounded border border-slate-700 bg-slate-900 p-2 text-xs text-slate-200" placeholder="可选：用自然语言补充你特别想看到的画面；留空则忠实依据正文……" />
      <ImageGenerationOptions v-model="options" />
      <div class="flex items-center gap-2"><select v-model="referenceRole" class="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"><option value="character">角色参考图</option><option value="style">画风参考图</option></select><label class="cursor-pointer rounded bg-slate-800 px-2 py-1 text-[10px] text-slate-300">选择参考图<input type="file" accept="image/png,image/jpeg,image/webp" multiple class="hidden" @change="chooseReferences" /></label><span class="truncate text-[10px] text-slate-500">{{ referenceFiles.length?referenceFiles.map(file=>file.name).join('、'):'未选择' }}</span></div>
      <p v-if="referenceFiles.length" class="text-[10px] text-amber-400/80">参考图会作为本局资产保存；当前内置基础工作流尚未接入参考图节点，因此暂时不会影响生成结果。</p>
      <div class="flex flex-wrap justify-end gap-2"><button @click="showForm=false" class="rounded bg-slate-700 px-3 py-1.5 text-xs">取消</button><button @click="generateDirect" :disabled="submitting || !prompt.trim()" title="把输入内容直接交给 ComfyUI，不调用提示词 AI" class="rounded border border-slate-600 px-3 py-1.5 text-xs text-slate-300 disabled:opacity-40">直接使用当前提示词</button><button @click="generateWithAI" :disabled="submitting" class="rounded bg-fuchsia-700 px-4 py-1.5 text-xs font-bold text-white hover:bg-fuchsia-600 disabled:opacity-50">{{ submitting?'正在创建任务…':'✨ AI 整理并开始生成' }}</button></div>
    </div>
    <div v-for="task in tasks" :key="task.id" class="mt-2 rounded-xl border border-fuchsia-900/60 bg-slate-950/80 p-3">
      <div class="flex items-center justify-between text-xs"><span class="text-fuchsia-300">🖼️ {{ statusText[task.status]||task.status }}</span><span class="font-mono text-[9px] text-slate-600">{{ task.id }}</span></div>
      <div v-if="['queued','compiling_prompt','ready','submitted','running'].includes(task.status)" class="mt-2"><div class="h-1.5 overflow-hidden rounded bg-slate-800"><div class="h-full w-1/3 animate-pulse rounded bg-fuchsia-500" /></div><p class="mt-1 text-[9px] text-slate-600">这是运行状态动画，不是生成百分比；当前 ComfyUI 核心 HTTP 接口未提供采样进度。</p><button @click="imageStore.cancel(task.id)" class="mt-2 text-[10px] text-slate-400 hover:text-rose-300">取消任务</button></div>
      <div v-else-if="task.status==='failed'" class="mt-2 text-xs text-rose-300">{{ task.error_message||'未知错误' }} <button @click="imageStore.retry(task.id)" class="ml-2 underline">重试</button></div>
      <div v-else-if="task.status==='cancelled'" class="mt-2 text-xs text-slate-500">任务已取消 <button @click="imageStore.retry(task.id)" class="ml-2 underline">重新运行</button></div>
      <div v-else-if="task.status==='succeeded'" class="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
        <img v-for="url in task.output_images" :key="url" :src="imageApi.absoluteImageUrl(url)" @click="selectedUrl=imageApi.absoluteImageUrl(url)" class="h-40 w-full cursor-zoom-in rounded-lg border border-slate-700 bg-black object-contain sm:h-52" />
      </div>
      <div v-if="['succeeded','failed','cancelled'].includes(task.status)" class="mt-2 flex justify-end gap-2 text-[10px]"><button @click="regenerate(task)" class="rounded bg-fuchsia-900/50 px-2 py-1 text-fuchsia-200">重新生成</button><template v-if="deleteConfirmId===task.id"><button @click="removeTask(task)" class="rounded bg-rose-700 px-2 py-1 text-white">确认删除</button><button @click="deleteConfirmId=''" class="rounded bg-slate-700 px-2 py-1">取消</button></template><button v-else @click="deleteConfirmId=task.id" class="rounded bg-rose-950/50 px-2 py-1 text-rose-300">删除</button></div>
    </div>
    <div v-if="selectedUrl" @click="selectedUrl=''" class="fixed inset-0 z-[140] flex cursor-zoom-out items-center justify-center bg-black/90 p-6"><img :src="selectedUrl" class="max-h-full max-w-full rounded-lg object-contain"></div>
  </div>
</template>
