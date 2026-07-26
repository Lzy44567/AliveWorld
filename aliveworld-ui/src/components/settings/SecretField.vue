<script setup>
import { computed, onBeforeUnmount, ref } from 'vue';

const props = defineProps({
  modelValue: { type: String, default: '' },
  configured: { type: Boolean, default: false },
  field: { type: String, required: true },
  label: { type: String, default: 'API Key' },
  placeholder: { type: String, default: '输入 API Key' },
  emptyStatus: { type: String, default: '未配置' },
});
const emit = defineEmits(['update:modelValue']);

const visible = ref(false);
const loading = ref(false);
const error = ref('');
const canReveal = computed(() => props.configured || Boolean(props.modelValue));
const status = computed(() => {
  if (visible.value) return '密钥已显示，仅保留在本次界面内';
  if (props.configured) return '已配置，密钥当前已隐藏';
  return props.emptyStatus;
});

function hide() {
  visible.value = false;
  error.value = '';
  emit('update:modelValue', '');
}

async function reveal() {
  error.value = '';
  if (props.modelValue) {
    visible.value = true;
    return;
  }
  loading.value = true;
  try {
    const response = await fetch('/api/v1/game/system_config/reveal-secret', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ field: props.field }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || '读取密钥失败');
    emit('update:modelValue', data.value || '');
    visible.value = true;
  } catch (caught) {
    error.value = caught.message || '读取密钥失败';
  } finally {
    loading.value = false;
  }
}

onBeforeUnmount(() => {
  if (visible.value) emit('update:modelValue', '');
});
</script>

<template>
  <div>
    <label class="text-xs text-slate-400 block mb-1">{{ label }}</label>
    <div class="flex gap-2">
      <input
        :type="visible ? 'text' : 'password'"
        :value="modelValue"
        :placeholder="configured ? '已配置；输入内容可替换原密钥' : placeholder"
        class="min-w-0 flex-1 rounded border border-slate-700 bg-slate-900 p-2 text-sm text-slate-200 outline-none"
        autocomplete="off"
        @input="emit('update:modelValue', $event.target.value)"
      />
      <button
        v-if="canReveal"
        type="button"
        :disabled="loading"
        class="shrink-0 rounded border border-slate-600 bg-slate-800 px-3 text-xs text-slate-300 hover:bg-slate-700 disabled:opacity-50"
        @click="visible ? hide() : reveal()"
      >
        {{ loading ? '读取中' : (visible ? '隐藏' : '显示') }}
      </button>
    </div>
    <p class="mt-1 text-[10px]" :class="configured ? 'text-emerald-500' : 'text-slate-500'">{{ status }}</p>
    <p v-if="error" class="mt-1 text-[10px] text-rose-400">{{ error }}</p>
  </div>
</template>
