<script setup>
import { computed, ref } from 'vue';
import { assetStore } from '../../store/assetStore';
import AssetCardPicker from './AssetCardPicker.vue';
const props = defineProps({ modelValue: Object, disabled: Boolean });
const emit = defineEmits(['update:modelValue']);
const picker = ref('');
const categories = [
  { key: 'worldbook', title: '世界书', group: 'worlds' },
  { key: 'player_character', title: '我扮演的角色', group: 'characters' },
  { key: 'style', title: '文风', group: 'styles' },
];
const current = computed(() => categories.find(item => item.key === picker.value));
function select(value) {
  emit('update:modelValue', { ...props.modelValue, [picker.value]: value });
}
</script>
<template>
  <section class="space-y-2" aria-label="开局资产">
    <p class="text-xs text-slate-400">选用已有资产（选填）</p>
    <div class="grid gap-2 sm:grid-cols-3">
      <button v-for="item in categories" :key="item.key" type="button" :disabled="disabled" :data-testid="`start-select-${item.key}`" class="rounded-lg border border-slate-600 bg-slate-900 p-3 text-left text-sm text-slate-200 disabled:opacity-50" @click="picker=item.key">
        <span class="block text-xs text-slate-400">{{ item.title }}</span>
        <span class="mt-1 block break-words">{{ modelValue[item.key] || '点击选择' }}</span>
      </button>
    </div>
    <p class="text-xs text-slate-500">复制到当前故事，不修改原卡。选择的角色由你扮演；更多人物和设定可在开始后载入。</p>
  </section>
  <AssetCardPicker v-if="current" :items="assetStore[current.group].global" :title="`选择${current.title}`" :model-value="modelValue[current.key]" empty-label="不载入" @update:model-value="select" @close="picker=''" />
</template>
