<script setup>
import { nextTick, ref, useAttrs, watch } from 'vue';

defineOptions({ inheritAttrs: false });

defineProps({
  label: { type: String, default: '长文本编辑' },
  placeholder: { type: String, default: '' },
  textareaClass: { type: [String, Array, Object], default: '' },
  wrapperClass: { type: [String, Array, Object], default: '' },
});
const model = defineModel({ type: String, default: '' });
const attrs = useAttrs();
const expanded = ref(false);
const inlineEditor = ref(null);
const expandedEditor = ref(null);

async function insertText(text) {
  const editor = expanded.value ? expandedEditor.value : inlineEditor.value;
  const start = editor?.selectionStart ?? model.value.length;
  const end = editor?.selectionEnd ?? start;
  model.value = `${model.value.slice(0, start)}${text}${model.value.slice(end)}`;
  await nextTick();
  const activeEditor = expanded.value ? expandedEditor.value : inlineEditor.value;
  activeEditor?.focus();
  activeEditor?.setSelectionRange(start + text.length, start + text.length);
}

defineExpose({ insertText });

watch(expanded, async value => {
  if (!value) return;
  await nextTick();
  expandedEditor.value?.focus();
});
</script>

<template>
  <div class="group/expandable-textarea relative min-w-0" :class="wrapperClass">
    <textarea ref="inlineEditor" v-model="model" v-bind="attrs" :aria-label="attrs['aria-label'] || label" :placeholder="placeholder" :class="textareaClass" class="block w-full pr-10" />
    <span
      role="button"
      tabindex="0"
      data-testid="expand-textarea"
      class="absolute right-2 top-2 rounded border border-slate-600/70 bg-slate-950/85 px-1.5 py-1 text-[10px] leading-none text-slate-400 opacity-45 transition hover:border-indigo-400 hover:text-white hover:opacity-100 focus:opacity-100 group-hover/expandable-textarea:opacity-100"
      :title="`展开编辑：${label}`"
      :aria-label="`展开编辑：${label}`"
      @click="expanded = true"
      @keydown.enter.prevent="expanded = true"
      @keydown.space.prevent="expanded = true"
    >⛶</span>
    <Teleport :to="inlineEditor?.closest('dialog') || 'body'">
      <div
        v-if="expanded"
        data-testid="expanded-textarea-dialog"
        class="fixed inset-0 z-[200] flex flex-col bg-slate-950/97 p-4 backdrop-blur-sm sm:p-6"
        role="dialog"
        aria-modal="true"
        :aria-label="`展开编辑：${label}`"
        @keydown.esc.stop.prevent="expanded = false"
      >
        <header class="mb-3 flex items-center justify-between gap-4">
          <div class="min-w-0"><h3 class="truncate font-bold text-slate-100">{{ label }}</h3><p class="mt-1 text-xs text-slate-500">Esc 或右上角按钮返回；内容会实时保留在原输入框中。</p></div>
          <button type="button" data-testid="expanded-textarea-close" @click="expanded = false" class="shrink-0 rounded bg-indigo-700 px-4 py-2 text-sm font-bold text-white hover:bg-indigo-600">完成</button>
        </header>
        <textarea ref="expandedEditor" v-model="model" v-bind="attrs" :aria-label="`${attrs['aria-label'] || label}（大屏编辑）`" :placeholder="placeholder" class="min-h-0 flex-1 resize-none rounded-xl border border-slate-700 bg-slate-900 p-5 text-base leading-7 text-slate-100 outline-none focus:border-indigo-500" />
      </div>
    </Teleport>
  </div>
</template>
