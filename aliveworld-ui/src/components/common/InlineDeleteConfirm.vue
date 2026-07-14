<script setup>
defineProps({
  active: { type: Boolean, default: false },
  confirmId: { type: [String, Number], required: true },
  compact: { type: Boolean, default: false },
});

defineEmits(['request', 'cancel', 'confirm']);
</script>

<template>
  <span
    :data-delete-confirm-id="active ? String(confirmId) : undefined"
    class="inline-flex shrink-0 items-center gap-1"
    :class="compact ? 'w-28' : 'w-32'"
  >
    <button
      v-if="!active"
      type="button"
      class="rounded text-rose-400 hover:bg-rose-950/60"
      :class="compact ? 'px-2 py-1 text-[9px]' : 'px-2 py-1 text-[10px]'"
      @click="$emit('request')"
    >删除</button>
    <template v-else>
      <button type="button" class="rounded bg-slate-700 text-slate-100 hover:bg-slate-600" :class="compact ? 'px-2 py-1 text-[9px]' : 'px-2 py-1 text-[10px]'" @click="$emit('cancel')">取消</button>
      <button type="button" class="rounded bg-rose-700 font-bold text-white hover:bg-rose-600" :class="compact ? 'px-2 py-1 text-[9px]' : 'px-2 py-1 text-[10px]'" @click="$emit('confirm')">确认删除</button>
    </template>
  </span>
</template>
