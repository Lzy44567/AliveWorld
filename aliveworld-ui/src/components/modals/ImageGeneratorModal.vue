<script setup>
import { ref } from 'vue';
import { configStore } from '../../store/configStore';
import { gameStore } from '../../store/gameStore';
import { imageStore } from '../../store/imageStore';
import { uiStore } from '../../store/uiStore';
import { fileToDataUrl, imageApi } from '../../api/imageApi';

const prompt = ref('');
const files = ref([]);
const role = ref('character');
const submitting = ref(false);
const context = uiStore.imageGeneratorContext;

const close = () => { if (!submitting.value) uiStore.modals.imageGenerator = false; };
const chooseFiles = event => { files.value = [...(event.target.files || [])]; };

const submit = async () => {
  const settings = configStore.globalSettings;
  if (!prompt.value.trim()) return uiStore.showToast('请填写立绘提示词', 'error');
  if (!settings.imageCheckpoint) return uiStore.showToast('请先在生图配置中选择 checkpoint', 'error');
  submitting.value = true;
  try {
    const references = [];
    for (const file of files.value) {
      const uploaded = await imageApi.uploadReference(gameStore.sessionId, { filename: file.name, role: role.value, data_url: await fileToDataUrl(file) });
      references.push({ path: uploaded.id, role: uploaded.role, label: uploaded.filename });
    }
    await imageStore.create(gameStore.sessionId, {
      intent: 'character_portrait', character_ids: [context.characterName], provider_id: 'comfyui', workflow_id: settings.imageWorkflowId,
      prompt: { positive: prompt.value.trim(), negative: settings.imageNegativePrompt, style_preference: settings.imageStylePreference, presentation_level: settings.imagePresentationLevel, width: 512, height: 768, references },
      context_snapshot: { character_name: context.characterName, character_description: context.description },
      provider_options: { base_url: settings.imageApiUrl, checkpoint: settings.imageCheckpoint }
    });
    uiStore.showToast('角色立绘已进入后台队列');
    uiStore.modals.imageGenerator = false;
  } catch (error) { uiStore.showToast(error.message, 'error'); }
  finally { submitting.value = false; }
};
</script>

<template>
  <div class="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
    <div class="w-full max-w-xl rounded-2xl border border-fuchsia-800/70 bg-aw_panel shadow-2xl">
      <header class="flex items-center justify-between border-b border-slate-700 p-4"><div><h2 class="font-bold text-fuchsia-300">🎨 生成角色立绘</h2><p class="text-[11px] text-slate-500">{{ context.characterName }} · 直接提示词模式</p></div><button @click="close" class="text-xl text-slate-400">✕</button></header>
      <main class="space-y-3 p-5">
        <div class="rounded-lg bg-slate-900/70 p-3 text-xs text-slate-400">角色资料：{{ context.description || '暂无简介，请在提示词中完整描述外观。' }}</div>
        <textarea v-model="prompt" rows="6" class="w-full rounded-lg border border-slate-700 bg-slate-950 p-3 text-sm text-slate-200" placeholder="描述角色外观、服装、姿态、构图和背景……" />
        <div class="flex items-center gap-2"><select v-model="role" class="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs"><option value="character">角色参考图</option><option value="style">画风参考图</option></select><label class="cursor-pointer rounded bg-slate-800 px-3 py-1 text-xs">选择参考图<input type="file" accept="image/png,image/jpeg,image/webp" multiple class="hidden" @change="chooseFiles" /></label><span class="truncate text-[10px] text-slate-500">{{ files.map(file => file.name).join('、') }}</span></div>
        <p v-if="files.length && configStore.globalSettings.imageWorkflowId === 'builtin_basic'" class="text-[10px] text-amber-400">内置基础工作流不会使用参考图；图片仍会保存，需换用带参考图输入的工作流。</p>
      </main>
      <footer class="flex justify-end gap-2 border-t border-slate-700 p-4"><button @click="close" class="rounded bg-slate-700 px-4 py-2 text-xs">取消</button><button @click="submit" :disabled="submitting" class="rounded bg-fuchsia-700 px-4 py-2 text-xs font-bold text-white disabled:opacity-50">{{ submitting ? '上传并提交中…' : '开始生成' }}</button></footer>
    </div>
  </div>
</template>
