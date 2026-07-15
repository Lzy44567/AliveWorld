<script setup>
import { computed, nextTick, ref, watch } from 'vue';

const props = defineProps({
  open: { type: Boolean, default: false },
  action: { type: String, default: 'clone' },
  currentName: { type: String, default: '' },
  kindLabel: { type: String, default: '资产' },
});
const emit = defineEmits(['cancel', 'confirm']);
const name = ref('');
const input = ref(null);
const isClone = computed(() => props.action === 'clone');

watch(() => [props.open, props.action, props.currentName], async () => {
  if (!props.open) return;
  name.value = isClone.value ? `${props.currentName} 副本` : props.currentName;
  await nextTick();
  input.value?.focus();
  input.value?.select();
}, { immediate: true });

const submit = () => {
  const value = name.value.trim();
  if (value) emit('confirm', value);
};
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-[150] flex items-center justify-center bg-black/75 p-4" @mousedown.self="$emit('cancel')">
      <section class="w-full max-w-md rounded-2xl border border-indigo-700/70 bg-slate-900 p-5 shadow-2xl" role="dialog" aria-modal="true">
        <h3 class="text-base font-bold text-slate-100">{{ isClone ? '克隆' : '重命名' }}{{ kindLabel }}</h3>
        <p class="mt-1 text-xs leading-relaxed text-slate-400">{{ isClone ? '创建一份独立副本，之后的修改不会影响原版。' : '内容不变，只更新名称与存储路径。' }}</p>
        <label class="mt-4 block text-xs font-bold text-slate-300">新名称</label>
        <input ref="input" v-model="name" @keydown.enter.prevent="submit" @keydown.esc.prevent="$emit('cancel')" maxlength="80" class="mt-2 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-indigo-500" />
        <div class="mt-5 flex justify-end gap-2">
          <button @click="$emit('cancel')" class="rounded-lg bg-slate-700 px-4 py-2 text-xs font-bold text-slate-200 hover:bg-slate-600">取消</button>
          <button @click="submit" :disabled="!name.trim()" class="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-500 disabled:opacity-40">确认{{ isClone ? '克隆' : '重命名' }}</button>
        </div>
      </section>
    </div>
  </Teleport>
</template>
