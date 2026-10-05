<script setup>
import { computed } from 'vue';
import { oocLength, oocText } from '../../utils/characterOoc.js';
const props = defineProps({ modelValue: { type: String, default: '' }, open: Boolean });
const emit = defineEmits(['update:modelValue', 'update:open']);
const count = computed(() => oocLength(props.modelValue));
</script>
<template>
  <div data-testid="character-ooc-input" class="text-xs space-y-2">
    <div class="flex items-center gap-3 flex-wrap">
      <button type="button" data-testid="character-ooc-toggle" :aria-expanded="open" class="text-slate-400 hover:text-indigo-200" @click="emit('update:open', !open)">{{ open ? '收起场外提示' : '场外提示' }}</button>
      <span v-if="oocText(modelValue)" data-testid="character-ooc-attached" :class="count>1000 ? 'text-rose-300' : 'text-amber-200'">本次含场外提示 · {{ count }} 字</span>
      <button v-if="modelValue" type="button" data-testid="character-ooc-clear" class="text-slate-500 hover:text-slate-200" @click="emit('update:modelValue', '')">清空场外提示</button>
    </div>
    <div v-if="open" class="rounded-lg border border-indigo-900/60 bg-slate-900/70 p-2">
      <p id="character-ooc-help" class="text-slate-400 mb-2">仅本轮，随台词发送；单独保存为生成说明，不作为角色经历。生成时会发送给所选模型。</p>
      <textarea data-testid="character-ooc-composer" :value="modelValue" rows="2" aria-label="本轮场外提示" aria-describedby="character-ooc-help" :aria-invalid="count>1000" class="w-full rounded bg-slate-950 border border-slate-700 p-2 text-slate-200 resize-y" placeholder="例如：这轮节奏慢一些，多表达角色自己的立场。Enter 换行。" @input="emit('update:modelValue', $event.target.value)"></textarea>
      <p :class="count>1000 ? 'text-rose-300' : 'text-slate-500'">{{ count }}/1000 字 · 不会修改角色卡或全局偏好。未提交草稿仅在当前页面保留，刷新页面可能丢失。</p>
    </div>
  </div>
</template>
