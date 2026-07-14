<script setup>
import { reactive, ref } from 'vue';
import { configStore } from '../../store/configStore';
import { gameStore } from '../../store/gameStore';
import { imageStore } from '../../store/imageStore';
import { uiStore } from '../../store/uiStore';
import { fileToDataUrl, imageApi } from '../../api/imageApi';
import ImageGenerationOptions from '../image/ImageGenerationOptions.vue';

const prompt = ref('');
const files = ref([]);
const role = ref('character');
const submitting = ref(false);
const context = uiStore.imageGeneratorContext;
const isGlobal = context.scope === 'global';
const options = reactive({ width:512, height:768, count:configStore.globalSettings.imageCount || 1, steps:configStore.globalSettings.imageSteps || 20, cfg:configStore.globalSettings.imageCfg || 7 });

const close = () => { if (!submitting.value) uiStore.modals.imageGenerator = false; };
const chooseFiles = event => { files.value = [...(event.target.files || [])]; };

const submit = async (direct = false) => {
  const settings = configStore.globalSettings;
  if (direct && !prompt.value.trim()) return uiStore.showToast('直接生成模式需要填写生图提示词', 'error');
  if (!settings.imageCheckpoint) return uiStore.showToast('请先在生图配置中选择生图模型', 'error');
  submitting.value = true;
  try {
    const references = [];
    for (const file of isGlobal ? [] : files.value) {
      const uploaded = await imageApi.uploadReference(gameStore.sessionId, { filename: file.name, role: role.value, data_url: await fileToDataUrl(file) });
      references.push({ path: uploaded.id, role: uploaded.role, label: uploaded.filename });
    }
    const task = {
      intent: 'character_portrait', character_ids: [context.characterName], provider_id: 'comfyui', workflow_id: settings.imageWorkflowId,
      prompt: { positive: direct ? prompt.value.trim() : '', negative: settings.imageNegativePrompt, style_preference: settings.imageStylePreference, presentation_level: settings.imagePresentationLevel, ...options, references },
      context_snapshot: { character_name: context.characterName, character_description: context.description, portrait_scope: isGlobal ? 'global' : 'local', auto_assign_portrait: true },
      provider_options: { base_url: settings.imageApiUrl, checkpoint: settings.imageCheckpoint }
    };
    const compile = {
      intent:'character_portrait', user_request:prompt.value, character_ids:[context.characterName], character_context:`${context.characterName}\n${context.description || ''}`,
      style_preference:settings.imageStylePreference, presentation_level:settings.imagePresentationLevel,
      model_name:settings.imageCheckpoint, model_profile:settings.imageModelProfiles?.[settings.imageCheckpoint] || ''
    };
    if (isGlobal) {
      const created = direct ? await imageApi.createGlobalPortraitTask(task) : await imageApi.compileAndCreateGlobalPortrait(task, compile);
      imageStore.watchLibraryTask('global', created);
    } else if (direct) await imageStore.create(gameStore.sessionId, task);
    else await imageStore.compileAndCreate(gameStore.sessionId, task, compile);
    uiStore.showToast(direct ? '角色立绘已进入后台队列' : 'AI 正在后台整理角色立绘提示词，完成后会自动生成');
    uiStore.modals.imageGenerator = false;
  } catch (error) { uiStore.showToast(error.message, 'error'); }
  finally { submitting.value = false; }
};

</script>

<template>
  <div class="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
    <div class="w-full max-w-xl rounded-2xl border border-fuchsia-800/70 bg-aw_panel shadow-2xl">
      <header class="flex items-center justify-between border-b border-slate-700 p-4"><div><h2 class="font-bold text-fuchsia-300">🎨 生成{{ isGlobal ? '全局' : '本局' }}角色立绘</h2><p class="text-[11px] text-slate-500">{{ context.characterName }} · AI 会按可长期复用的角色立绘整理提示词</p></div><button @click="close" class="text-xl text-slate-400">✕</button></header>
      <main class="space-y-3 p-5">
        <div class="rounded-lg bg-slate-900/70 p-3 text-xs text-slate-400">角色资料：{{ context.description || '暂无简介，请在提示词中完整描述外观。' }}</div>
        <textarea v-model="prompt" rows="5" class="w-full rounded-lg border border-slate-700 bg-slate-950 p-3 text-sm text-slate-200" placeholder="可选：用自然语言补充外观、服装、姿态或背景；留空则根据角色资料生成……" />
        <ImageGenerationOptions v-model="options" />
        <div v-if="!isGlobal" class="flex items-center gap-2"><select v-model="role" class="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs"><option value="character">角色参考图</option><option value="style">画风参考图</option></select><label class="cursor-pointer rounded bg-slate-800 px-3 py-1 text-xs">选择参考图<input type="file" accept="image/png,image/jpeg,image/webp" multiple class="hidden" @change="chooseFiles" /></label><span class="truncate text-[10px] text-slate-500">{{ files.map(file => file.name).join('、') }}</span></div>
        <p v-else class="text-[10px] text-slate-500">全局立绘不依赖任何存档；全局参考图将在角色工坊版本统一管理。</p>
        <p v-if="files.length" class="text-[10px] text-amber-400">参考图会作为本局资产安全保存；当前版本尚未把参考图注入 ComfyUI 工作流，首版仍按文字提示生成。</p>
      </main>
      <footer class="flex flex-wrap justify-end gap-2 border-t border-slate-700 p-4"><button @click="close" class="rounded bg-slate-700 px-4 py-2 text-xs">取消</button><button @click="submit(true)" :disabled="submitting || !prompt.trim()" class="rounded border border-slate-600 px-4 py-2 text-xs disabled:opacity-40">直接使用当前提示词</button><button @click="submit(false)" :disabled="submitting" class="rounded bg-fuchsia-700 px-4 py-2 text-xs font-bold text-white disabled:opacity-50">{{ submitting ? '正在创建任务…' : '✨ AI 整理并开始生成' }}</button></footer>
    </div>
  </div>
</template>
