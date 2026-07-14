<script setup>
import { computed, ref } from 'vue';
import { configStore } from '../../store/configStore';
import { gameStore } from '../../store/gameStore';
import { imageStore } from '../../store/imageStore';
import { uiStore } from '../../store/uiStore';
import { fileToDataUrl, imageApi } from '../../api/imageApi';

const props = defineProps({ message: { type: Object, required: true } });
const tasks = computed(() => imageStore.forMessage(props.message.id));
const showForm = ref(false);
const prompt = ref('');
const intent = ref('scene_cg');
const submitting = ref(false);
const compiling = ref(false);
const notes = ref('');
const referenceFiles = ref([]);
const referenceRole = ref('character');
const statusText = { queued:'等待提示词', compiling_prompt:'整理提示词', ready:'准备提交', submitted:'已提交', running:'生成中', succeeded:'已完成', failed:'生成失败', cancelled:'已取消' };

const chooseReferences = event => { referenceFiles.value = [...(event.target.files || [])]; };

const compilePrompt = async () => {
  compiling.value = true;
  try {
    const result = await imageApi.compilePrompt(gameStore.sessionId, {
      intent: intent.value, user_request: prompt.value, source_message_id: props.message.id,
      style_preference: configStore.globalSettings.imageStylePreference,
      presentation_level: configStore.globalSettings.imagePresentationLevel
    });
    prompt.value = result.positive;
    if (result.negative) configStore.globalSettings.imageNegativePrompt = result.negative;
    notes.value = result.notes;
    uiStore.showToast('AI 已整理提示词，请确认后生成');
  } catch (error) { uiStore.showToast(error.message, 'error'); }
  finally { compiling.value = false; }
};

const generate = async () => {
  const settings = configStore.globalSettings;
  if (!prompt.value.trim()) return uiStore.showToast('请填写生图提示词', 'error');
  if (!settings.imageCheckpoint) return uiStore.showToast('请先在“设置 → 生图配置”选择 checkpoint', 'error');
  submitting.value = true;
  try {
    const references = [];
    for (const file of referenceFiles.value) {
      const uploaded = await imageApi.uploadReference(gameStore.sessionId, { filename:file.name, role:referenceRole.value, data_url:await fileToDataUrl(file) });
      references.push({ path:uploaded.id, role:uploaded.role, label:uploaded.filename });
    }
    await imageStore.create(gameStore.sessionId, {
      intent:intent.value, source_message_id:props.message.id, provider_id:'comfyui', workflow_id:settings.imageWorkflowId,
      prompt:{ positive:prompt.value.trim(), negative:settings.imageNegativePrompt, style_preference:settings.imageStylePreference, presentation_level:settings.imagePresentationLevel, width:intent.value==='scene_cg'?768:512, height:768, references },
      context_snapshot:{ story_text:props.message.content }, provider_options:{ base_url:settings.imageApiUrl, checkpoint:settings.imageCheckpoint }
    });
    showForm.value = false;
    prompt.value = '';
    referenceFiles.value = [];
    uiStore.showToast('生图任务已进入后台队列');
  } catch (error) { uiStore.showToast(error.message, 'error'); }
  finally { submitting.value = false; }
};
</script>

<template>
  <div class="mt-2">
    <button v-if="!showForm" @click="showForm=true" class="rounded border border-fuchsia-800/60 bg-fuchsia-950/20 px-2 py-1 text-[11px] text-fuchsia-300 hover:text-fuchsia-200">🎨 生成此处 CG</button>
    <div v-else class="space-y-2 rounded-xl border border-fuchsia-800/60 bg-slate-950/90 p-3">
      <div class="flex gap-2"><select v-model="intent" class="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"><option value="scene_cg">场景 CG</option><option value="character_cg">角色 CG</option></select><span class="self-center text-[10px] text-slate-500">直接提示词模式，不调用 LLM</span></div>
      <textarea v-model="prompt" rows="3" class="w-full resize-y rounded border border-slate-700 bg-slate-900 p-2 text-xs text-slate-200" placeholder="描述希望生成的画面……" />
      <div class="flex items-center gap-2"><button @click="compilePrompt" :disabled="compiling" class="rounded bg-violet-900/70 px-2 py-1 text-[10px] text-violet-200 disabled:opacity-50">{{ compiling?'AI 整理中…':'✨ 让 AI 根据正文整理提示词' }}</button><span v-if="notes" class="text-[10px] text-slate-500">{{ notes }}</span></div>
      <div class="flex items-center gap-2"><select v-model="referenceRole" class="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"><option value="character">角色参考图</option><option value="style">画风参考图</option></select><label class="cursor-pointer rounded bg-slate-800 px-2 py-1 text-[10px] text-slate-300">选择参考图<input type="file" accept="image/png,image/jpeg,image/webp" multiple class="hidden" @change="chooseReferences" /></label><span class="truncate text-[10px] text-slate-500">{{ referenceFiles.length?referenceFiles.map(file=>file.name).join('、'):'未选择' }}</span></div>
      <p v-if="referenceFiles.length" class="text-[10px] text-amber-400/80">参考图会作为本局资产安全保存；当前版本尚未把参考图注入 ComfyUI 工作流，首版仍按文字提示生成。</p>
      <div class="flex justify-end gap-2"><button @click="showForm=false" class="rounded bg-slate-700 px-3 py-1 text-xs">取消</button><button @click="generate" :disabled="submitting" class="rounded bg-fuchsia-700 px-3 py-1 text-xs text-white hover:bg-fuchsia-600 disabled:opacity-50">{{ submitting?'提交中…':'开始生成' }}</button></div>
    </div>
    <div v-for="task in tasks" :key="task.id" class="mt-2 rounded-xl border border-fuchsia-900/60 bg-slate-950/80 p-3">
      <div class="flex items-center justify-between text-xs"><span class="text-fuchsia-300">🖼️ {{ statusText[task.status]||task.status }}</span><span class="font-mono text-[9px] text-slate-600">{{ task.id }}</span></div>
      <div v-if="['queued','compiling_prompt','ready','submitted','running'].includes(task.status)" class="mt-2"><div class="h-1.5 overflow-hidden rounded bg-slate-800"><div class="h-full bg-fuchsia-500 transition-all" :class="task.progress?'':'w-1/3 animate-pulse'" :style="task.progress?{width:`${task.progress*100}%`}:{}" /></div><button @click="imageStore.cancel(task.id)" class="mt-2 text-[10px] text-slate-400 hover:text-rose-300">取消任务</button></div>
      <div v-else-if="task.status==='failed'" class="mt-2 text-xs text-rose-300">{{ task.error_message||'未知错误' }} <button @click="imageStore.retry(task.id)" class="ml-2 underline">重试</button></div>
      <div v-else-if="task.status==='cancelled'" class="mt-2 text-xs text-slate-500">任务已取消 <button @click="imageStore.retry(task.id)" class="ml-2 underline">重新生成</button></div>
      <div v-else-if="task.status==='succeeded'" class="mt-2 grid gap-2"><img v-for="url in task.output_images" :key="url" :src="imageApi.absoluteImageUrl(url)" class="max-h-[32rem] rounded-lg border border-slate-700 bg-black object-contain" /></div>
    </div>
  </div>
</template>
