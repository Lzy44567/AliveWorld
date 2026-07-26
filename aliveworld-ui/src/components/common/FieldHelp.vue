<script setup>
import { computed, nextTick, onBeforeUnmount, ref } from 'vue';

defineProps({ text: { type: String, required: true } });

const anchor = ref(null);
const tooltip = ref(null);
const visible = ref(false);
const position = ref({ left: 8, top: 8, width: 256 });
const tooltipStyle = computed(() => ({
  left: `${position.value.left}px`,
  top: `${position.value.top}px`,
  width: `${position.value.width}px`,
}));

const placeTooltip = () => {
  if (!anchor.value) return;
  const rect = anchor.value.getBoundingClientRect();
  const padding = 8;
  const width = Math.min(256, Math.max(180, window.innerWidth - padding * 2));
  const tooltipHeight = tooltip.value?.offsetHeight || 92;
  const left = Math.min(
    window.innerWidth - width - padding,
    Math.max(padding, rect.left + rect.width / 2 - width / 2),
  );
  const top = rect.top >= tooltipHeight + 12
    ? rect.top - tooltipHeight - 8
    : Math.min(window.innerHeight - tooltipHeight - padding, rect.bottom + 8);
  position.value = { left, top: Math.max(padding, top), width };
};

const show = () => {
  visible.value = true;
  nextTick(placeTooltip);
  window.addEventListener('resize', placeTooltip);
  window.addEventListener('scroll', placeTooltip, true);
};
const hide = () => {
  visible.value = false;
  window.removeEventListener('resize', placeTooltip);
  window.removeEventListener('scroll', placeTooltip, true);
};
onBeforeUnmount(hide);
</script>

<template>
  <span
    ref="anchor"
    class="ml-1 inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full border border-slate-500 text-[9px] text-slate-400"
    tabindex="0"
    @mouseenter="show"
    @mouseleave="hide"
    @focus="show"
    @blur="hide"
  >?
    <Teleport to="body">
      <span ref="tooltip" v-if="visible" class="pointer-events-none fixed z-[100] max-h-[calc(100vh-1rem)] overflow-y-auto rounded-lg border border-slate-700 bg-slate-950 p-2 text-left text-[10px] font-normal leading-relaxed text-slate-300 shadow-xl" :style="tooltipStyle">{{ text }}</span>
    </Teleport>
  </span>
</template>
