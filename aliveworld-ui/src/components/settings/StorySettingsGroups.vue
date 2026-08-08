<script setup>
import { computed } from 'vue';
import FieldHelp from '../common/FieldHelp.vue';
import StoryMemoryStatus from './StoryMemoryStatus.vue';
import { STORY_SETTING_GROUPS } from '../../utils/storySettingDefinitions';

const props = defineProps({
  settings: { type: Object, required: true },
  showMemoryStatus: { type: Boolean, default: false },
  showAdvanced: { type: Boolean, default: false }
});
const visibleGroups = computed(() => STORY_SETTING_GROUPS.filter(group => props.showAdvanced || !group.advanced));

function normalizeNumber(item) {
  const parsed = Number.parseInt(props.settings[item.key], 10);
  const fallback = item.key === 'targetStoryLength' ? 500 : item.min;
  props.settings[item.key] = Math.max(item.min, Math.min(item.max, Number.isFinite(parsed) ? parsed : fallback));
}
</script>

<template>
  <div class="space-y-3">
    <details v-for="group in visibleGroups" :key="group.id" :open="group.open" class="setting-group">
      <summary class="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3">
        <span class="text-xs font-bold" :class="group.advanced ? 'text-slate-300' : 'text-emerald-300'">{{ group.title }}</span>
        <span class="text-[10px] text-slate-500">展开 / 收起</span>
      </summary>
      <div class="border-t border-slate-700/70 p-3">
        <p v-if="group.description" class="mb-3 text-[10px] leading-relaxed text-slate-500">{{ group.description }}</p>
        <div class="grid grid-cols-1 gap-2 xl:grid-cols-2">
          <label v-for="item in group.items" :key="item.key" class="setting-row">
            <span class="min-w-0"><span>{{ item.label }}</span><FieldHelp :text="item.help" /></span>
            <span v-if="item.type==='number'" class="flex shrink-0 items-center gap-1 text-[10px] text-slate-500">
              <input type="number" v-model.number="settings[item.key]" :min="item.min" :max="item.max" :step="item.step" class="w-20 rounded border border-slate-600 bg-slate-950 px-2 py-1 text-right text-xs text-slate-200" @change="normalizeNumber(item)">
              {{ item.suffix }}
            </span>
            <input v-else type="checkbox" v-model="settings[item.key]">
          </label>
        </div>
        <StoryMemoryStatus v-if="showMemoryStatus && group.id === 'memory'" class="mt-3" />
      </div>
    </details>
  </div>
</template>

<style scoped>
.setting-group { overflow: visible; border: 1px solid rgb(51 65 85); border-radius: .75rem; background: rgb(30 41 59 / .28); }
.setting-group[open] { background: rgb(30 41 59 / .42); }
.setting-row { display: flex; align-items: center; justify-content: space-between; gap: .75rem; cursor: pointer; border: 1px solid rgb(51 65 85); border-radius: .5rem; background: rgb(15 23 42 / .55); padding: .65rem .75rem; font-size: .75rem; color: rgb(203 213 225); }
.setting-row:hover { border-color: rgb(100 116 139); }
input[type="checkbox"] { width: 1rem; height: 1rem; flex: none; accent-color: rgb(99 102 241); }
</style>
