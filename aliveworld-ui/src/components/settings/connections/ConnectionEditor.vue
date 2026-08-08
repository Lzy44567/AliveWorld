<script setup>
import { computed, reactive, ref, watch } from 'vue';
import FieldHelp from '../../common/FieldHelp.vue';
import ModelCombobox from './ModelCombobox.vue';
import { connectionStore } from '../../../store/connectionStore';
import { configStore } from '../../../store/configStore';
import { uiStore } from '../../../store/uiStore';

const props = defineProps({
  profile: { type: Object, default: null },
  category: { type: String, default: 'text' },
});
const emit = defineEmits(['close', 'saved']);

const saving = ref(false);
const testing = ref(false);
const revealing = ref(false);
const secretVisible = ref(false);

const presets = {
  text: [
    { id: 'deepseek', label: 'DeepSeek', baseUrl: 'https://api.deepseek.com', model: 'deepseek-v4-flash' },
    { id: 'openai', label: 'OpenAI', baseUrl: 'https://api.openai.com/v1', model: '' },
    { id: 'local', label: '本地兼容接口', baseUrl: 'http://127.0.0.1:1234/v1', model: '' },
    { id: 'custom', label: '自定义兼容接口', baseUrl: '', model: '' },
  ],
  image: [
    { id: 'comfyui', label: '本地 ComfyUI', baseUrl: 'http://127.0.0.1:8188', model: '' },
  ],
};

const form = reactive({});
const isText = computed(() => form.category === 'text');
const title = computed(() => props.profile ? '编辑接口' : `新增${props.category === 'image' ? '生图' : '语言'}接口`);

function reset() {
  const category = props.profile?.category || props.category;
  Object.assign(form, {
    name: props.profile?.name || (category === 'image' ? '本地 ComfyUI' : '新语言接口'),
    category,
    protocol: props.profile?.protocol || (category === 'image' ? 'comfyui' : 'openai_compatible'),
    providerHint: props.profile?.provider_hint || (category === 'image' ? 'comfyui' : 'custom'),
    baseUrl: props.profile?.base_url || (category === 'image' ? 'http://127.0.0.1:8188' : ''),
    apiKey: '',
    defaultModel: props.profile?.default_model || '',
    enabled: props.profile?.enabled ?? true,
    advancedOptions: props.profile?.advanced_options || {},
    clearApiKey: false,
  });
  secretVisible.value = false;
}
watch(() => [props.profile, props.category], reset, { immediate: true });

function choosePreset(preset) {
  form.providerHint = preset.id;
  form.baseUrl = preset.baseUrl;
  if (!props.profile && preset.model) form.defaultModel = preset.model;
  if (!props.profile) form.name = preset.label;
}

async function revealSecret() {
  if (!props.profile) {
    secretVisible.value = true;
    return;
  }
  revealing.value = true;
  try {
    const data = await connectionStore.reveal(props.profile.id);
    form.apiKey = data.value || '';
    secretVisible.value = true;
  } catch (error) {
    uiStore.showToast(error.message, 'error');
  } finally {
    revealing.value = false;
  }
}

async function save(testAfter = false) {
  saving.value = true;
  try {
    const saved = props.profile
      ? await connectionStore.update(props.profile.id, form)
      : await connectionStore.create(form);
    if (testAfter) {
      testing.value = true;
      await connectionStore.test(saved.id);
      uiStore.showToast('接口保存并测试成功');
    } else {
      uiStore.showToast('接口配置已保存');
    }
    await configStore.fetchFromBackend();
    emit('saved', saved);
    emit('close');
  } catch (error) {
    uiStore.showToast(error.message, 'error');
  } finally {
    saving.value = false;
    testing.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm" @mousedown.self="emit('close')">
      <section class="flex max-h-[88vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-cyan-700/60 bg-slate-900 shadow-2xl">
        <header class="flex items-center justify-between border-b border-slate-700 px-5 py-4">
          <div>
            <h3 class="text-lg font-bold text-slate-100">{{ title }}</h3>
            <p class="mt-1 text-[10px] text-slate-500">密钥只保存在本机 UserData，不进入故事、日志或发行包。</p>
          </div>
          <button class="text-xl text-slate-400 hover:text-white" @click="emit('close')">✕</button>
        </header>

        <div class="custom-scrollbar flex-1 space-y-5 overflow-y-auto p-5">
          <label class="block">
            <span class="mb-1 flex items-center text-xs font-bold text-slate-300">接口名称<FieldHelp text="仅用于你自己辨认，例如“DeepSeek 正文”或“本地 ComfyUI”。它不等于模型名。" /></span>
            <input v-model="form.name" class="connection-field" placeholder="给这条接口起一个容易辨认的名称">
          </label>

          <section>
            <div class="mb-2 text-xs font-bold text-slate-300">接口平台</div>
            <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <button
                v-for="preset in presets[form.category]"
                :key="preset.id"
                class="rounded-xl border px-3 py-3 text-xs transition"
                :class="form.providerHint===preset.id?'border-cyan-500 bg-cyan-950/50 text-cyan-200':'border-slate-700 bg-slate-800 text-slate-400 hover:border-slate-500'"
                @click="choosePreset(preset)"
              >{{ preset.label }}</button>
            </div>
            <p v-if="isText" class="mt-2 text-[10px] leading-relaxed text-slate-500">当前完整支持 OpenAI-compatible 协议。平台预设只帮助填写地址，不会伪装成尚未实现的原生协议。</p>
          </section>

          <label class="block">
            <span class="mb-1 flex items-center text-xs font-bold text-slate-300">接口地址<FieldHelp text="服务商提供的 Base URL。DeepSeek、OpenAI 和常见本地兼容服务的地址并不相同。" /></span>
            <input v-model="form.baseUrl" class="connection-field" placeholder="https://...">
          </label>

          <label v-if="isText" class="block">
            <span class="mb-1 flex items-center text-xs font-bold text-slate-300">API Key<FieldHelp text="从对应服务商控制台获取。编辑时留空表示保持原密钥，不会把已保存密钥自动传回浏览器。" /></span>
            <div class="flex gap-2">
              <input v-model="form.apiKey" :type="secretVisible?'text':'password'" class="connection-field min-w-0 flex-1" :placeholder="profile?.api_key_configured?'已配置；留空保持原密钥':'输入 API Key'" autocomplete="off">
              <button v-if="profile?.api_key_configured || form.apiKey" class="rounded-lg border border-slate-600 bg-slate-800 px-3 text-xs text-slate-300" :disabled="revealing" @click="secretVisible?(secretVisible=false):revealSecret()">{{ revealing?'读取中':(secretVisible?'隐藏':'显示') }}</button>
            </div>
            <label v-if="profile?.api_key_configured" class="mt-2 flex items-center gap-2 text-[10px] text-rose-300"><input v-model="form.clearApiKey" type="checkbox">保存时清除原密钥</label>
          </label>

          <label v-if="isText" class="block">
            <span class="mb-1 flex items-center text-xs font-bold text-slate-300">默认模型<FieldHelp text="这条接口默认调用的模型。高级功能分配仍可让某个功能临时覆盖模型名，而不重复保存 API Key。" /></span>
            <ModelCombobox v-model="form.defaultModel" :profile-id="profile?.id || ''" />
          </label>

          <details class="rounded-xl border border-slate-700 bg-slate-950/40 p-3">
            <summary class="cursor-pointer text-xs font-bold text-slate-400">高级状态</summary>
            <p class="mt-2 text-[10px] text-slate-500">接口启停已移到连接卡片；这里保留其他服务商高级参数的后续扩展位置。</p>
          </details>
        </div>

        <footer class="flex flex-wrap justify-end gap-2 border-t border-slate-700 bg-slate-950/70 px-5 py-4">
          <button class="rounded-lg bg-slate-700 px-4 py-2 text-xs text-slate-200" @click="emit('close')">取消</button>
          <button class="rounded-lg bg-slate-700 px-4 py-2 text-xs font-bold text-white disabled:opacity-50" :disabled="saving" @click="save(false)">保存</button>
          <button class="rounded-lg bg-cyan-700 px-4 py-2 text-xs font-bold text-white disabled:opacity-50" :disabled="saving" @click="save(true)">{{ testing?'正在测试…':'保存并测试' }}</button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.connection-field {
  @apply w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-200 outline-none transition focus:border-cyan-500;
}
</style>
