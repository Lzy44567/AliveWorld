<script setup>
import { ref } from 'vue';
import { assetApi } from '../../api/assetApi.js';
import ExpandableTextarea from '../common/ExpandableTextarea.vue';
import { cardOpening } from '../../utils/characterOpening.js';
const props = defineProps({ card: String, disabled: Boolean });
const model = defineModel({ type: String, default: '' });
const loading = ref(false), error = ref('');
async function adopt() {
  if (!props.card || loading.value || props.disabled) return;
  const key = props.card; loading.value = true; error.value = '';
  try {
    const data = await assetApi.getAssetDetail('characters', key);
    if (props.card !== key || props.disabled) return;
    const content = cardOpening(data.parsed);
    if (!content) { error.value = '此卡没有有效的独立开场字段，可手动填写。'; return; }
    if (model.value.trim() && !window.confirm('采用角色卡开场将覆盖当前开场草稿，继续？')) return;
    model.value = content;
  } catch (e) { error.value = e.message; } finally { loading.value = false; }
}
</script>
<template>
  <details data-testid="character-opening-editor" class="rounded-lg border border-slate-700 p-3">
    <summary class="cursor-pointer text-sm">角色开场（可选，默认空）</summary>
    <p class="mt-2 text-xs text-slate-400">留空则由你先发言；切换角色不会替换此草稿。预设开场不是你已做过的行动。</p>
    <button type="button" data-testid="character-use-card-opening" class="my-2 text-xs text-indigo-300 underline" :disabled="disabled || loading || !card" @click="adopt">{{ loading ? '读取中…' : '使用角色卡开场' }}</button>
    <ExpandableTextarea v-model="model" data-testid="character-opening-input" label="角色开场" rows="4" :disabled="disabled" placeholder="角色的第一段话或开场情景；默认留空" textarea-class="rounded-lg border border-slate-700 bg-slate-950 p-3 text-sm" />
    <p class="mt-1 text-xs" :class="Array.from(model).length>8000?'text-rose-300':'text-slate-500'">{{ Array.from(model).length }} / 8000 字符</p>
    <p v-if="error" class="mt-2 text-xs text-amber-300">{{ error }}</p>
  </details>
</template>
