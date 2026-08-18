<script setup>
import { computed, ref } from 'vue';
import { externalAssetApi } from '../../api/externalAssetApi';
import { assetStore } from '../../store/assetStore';
import { uiStore } from '../../store/uiStore';

const props = defineProps({ kind: { type: String, required: true } });
const emit = defineEmits(['close', 'imported']);
const file = ref(null);
const preview = ref(null);
const name = ref('');
const busy = ref(false);
const error = ref('');
const label = computed(() => props.kind === 'character' ? '外部角色卡' : '外部世界书');
const accept = computed(() => props.kind === 'character' ? '.json,.png,.apng' : '.json');

async function choose(event) {
  const selected = event.target.files?.[0];
  event.target.value = '';
  if (!selected) return;
  busy.value = true;
  error.value = '';
  try {
    preview.value = await externalAssetApi.inspect(selected, props.kind);
    file.value = selected;
    name.value = preview.value.suggested_name;
  } catch (cause) {
    error.value = cause.message || '无法读取外部资产';
    preview.value = null;
    file.value = null;
  } finally { busy.value = false; }
}

async function commit() {
  if (!file.value || !name.value.trim()) return;
  busy.value = true;
  error.value = '';
  try {
    const result = await externalAssetApi.import(file.value, props.kind, name.value.trim());
    await assetStore.fetchAssets();
    uiStore.showToast(`已导入${props.kind === 'character' ? '角色卡' : '世界书'}“${result.name}”`);
    emit('imported', result);
    emit('close');
  } catch (cause) { error.value = cause.message || '导入失败'; }
  finally { busy.value = false; }
}
</script>

<template>
  <div class="fixed inset-0 z-[70] flex items-center justify-center bg-black/85 p-4" @click.self="emit('close')">
    <section role="dialog" :aria-label="`导入${label}`" class="flex max-h-[86vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-cyan-800 bg-slate-950 shadow-2xl">
      <header class="flex items-start justify-between border-b border-slate-800 px-5 py-4">
        <div><h3 class="font-black text-cyan-300">⇩ 导入{{ label }}</h3><p class="mt-1 text-xs text-slate-500">先检查映射结果，再写入个人资产库；不会自动载入故事。</p></div>
        <button class="text-slate-500 hover:text-white" @click="emit('close')">✕</button>
      </header>
      <div class="min-h-0 flex-1 space-y-4 overflow-y-auto p-5 custom-scrollbar">
        <label class="flex cursor-pointer items-center justify-center rounded-xl border border-dashed border-cyan-800 bg-cyan-950/20 p-6 text-sm font-bold text-cyan-300 hover:bg-cyan-950/40">
          {{ busy ? '正在检查…' : `选择${label}文件` }}
          <input data-testid="external-asset-file" type="file" :accept="accept" class="hidden" :disabled="busy" @change="choose">
        </label>
        <p v-if="error" role="alert" class="rounded-lg border border-rose-800 bg-rose-950/40 p-3 text-xs text-rose-200">{{ error }}</p>
        <template v-if="preview">
          <div class="grid gap-3 sm:grid-cols-2">
            <div class="rounded-xl border border-slate-800 bg-slate-900/70 p-3"><p class="text-[10px] text-slate-500">识别格式</p><p class="mt-1 text-sm font-bold text-slate-200">{{ preview.source_format }} · {{ preview.source_version }}</p></div>
            <div class="rounded-xl border border-slate-800 bg-slate-900/70 p-3"><p class="text-[10px] text-slate-500">图片立绘</p><p class="mt-1 text-sm font-bold" :class="preview.has_portrait?'text-emerald-300':'text-slate-500'">{{ preview.has_portrait ? '随 PNG 一同导入' : '无' }}</p></div>
          </div>
          <label class="block"><span class="mb-1 block text-xs font-bold text-slate-400">导入后的名称</span><input data-testid="external-asset-name" v-model="name" class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"></label>
          <section class="rounded-xl border border-emerald-900/70 bg-emerald-950/20 p-3"><h4 class="text-xs font-bold text-emerald-300">已原生映射</h4><ul class="mt-2 space-y-1 text-xs text-slate-300"><li v-for="item in preview.mapped_fields" :key="item">✓ {{ item }}</li></ul></section>
          <section v-if="preview.degraded_fields.length" class="rounded-xl border border-amber-900/70 bg-amber-950/20 p-3"><h4 class="text-xs font-bold text-amber-300">降级处理</h4><ul class="mt-2 space-y-1 text-xs leading-5 text-slate-300"><li v-for="item in preview.degraded_fields" :key="item">△ {{ item }}</li></ul></section>
          <section v-if="preview.preserved_fields.length" class="rounded-xl border border-indigo-900/70 bg-indigo-950/20 p-3"><h4 class="text-xs font-bold text-indigo-300">仅保留，当前不执行</h4><p class="mt-2 break-words text-xs leading-5 text-slate-400">{{ preview.preserved_fields.join('、') }}</p></section>
          <p v-for="item in preview.warnings" :key="item" class="rounded-lg bg-rose-950/30 p-3 text-xs text-rose-200">⚠ {{ item }}</p>
        </template>
      </div>
      <footer class="flex justify-end gap-2 border-t border-slate-800 px-5 py-4"><button class="rounded bg-slate-700 px-4 py-2 text-sm" @click="emit('close')">取消</button><button data-testid="external-asset-import" class="rounded bg-cyan-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-40" :disabled="busy || !preview || !name.trim()" @click="commit">确认导入</button></footer>
    </section>
  </div>
</template>
