<script setup>
import { computed } from 'vue';

const props = defineProps({ modelValue: { type: String, default: '' } });
const emit = defineEmits(['update:modelValue']);

const systemTags = [
  ['绝对规则', '世界客观规律或不可随意违反的规则'],
  ['常驻', '世界书启用时始终进入上下文'],
  ['传闻', '世界中的说法，真实性尚未确认'],
  ['玩家设定', '玩家明确建立的设定'],
  ['AI推断', '由正文或世界书 AI 推导'],
  ['Overseer推断', '由暗流统筹发现的候选设定'],
  ['待确认', '尚未正式成为世界事实，不参与检索'],
  ['待删除', '已停用并等待玩家确认删除'],
];
const help = computed(() => systemTags.map(([tag, desc]) => `${tag}：${desc}`).join('\n'));

const addTag = (tag) => {
  const tags = props.modelValue.split(/[,，]/).map(item => item.trim()).filter(Boolean);
  if (!tags.includes(tag)) tags.push(tag);
  emit('update:modelValue', tags.join(', '));
};
</script>

<template>
  <div>
    <div class="mb-1 flex items-center gap-1">
      <slot name="label"><span class="text-xs font-bold text-slate-400">标签</span></slot>
      <span class="flex h-4 w-4 cursor-help items-center justify-center rounded-full border border-slate-500 text-[10px] text-slate-400" :title="help" tabindex="0">?</span>
    </div>
    <input :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" class="w-full rounded-lg border border-slate-700 bg-[#0d0d12] px-3 py-2 text-sm text-slate-200" placeholder="输入自由标签，或点击下方系统标签" />
    <div class="mt-1.5 flex flex-wrap gap-1">
      <button v-for="([tag, desc]) in systemTags" :key="tag" type="button" @click="addTag(tag)" :title="desc" class="rounded border border-slate-700 bg-slate-800 px-1.5 py-0.5 text-[9px] text-slate-400 hover:border-indigo-500 hover:text-indigo-300">+ {{ tag }}</button>
    </div>
  </div>
</template>
