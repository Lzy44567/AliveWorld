<script setup>
import { ref } from 'vue';
import { uiStore } from '../../store/uiStore';
import { copyText } from '../../utils/clipboard';

const props = defineProps({ text: { type: [String, Object, Array], default: '' } });
const busy = ref(false);

const copy = async () => {
  if (busy.value) return;
  busy.value = true;
  const copied = await copyText(props.text);
  uiStore.showToast(copied ? '内容已复制' : '复制失败，请拖选文字后按 Ctrl+C', copied ? 'success' : 'error');
  busy.value = false;
};
</script>

<template>
  <button type="button" data-testid="copy-text" title="复制内容" aria-label="复制内容" class="rounded-md border border-slate-600/70 bg-slate-950/70 px-2 py-1 text-[10px] text-slate-400 shadow transition hover:border-cyan-600 hover:text-cyan-200" @click.stop="copy">
    {{ busy ? '…' : '复制' }}
  </button>
</template>
