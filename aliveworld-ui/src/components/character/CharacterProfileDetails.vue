<script setup>
defineProps({ profile: { type: Object, required: true } });
const fields = [
  ['description', '人设与背景'], ['personality', '性格资料'], ['scenario', '初始场景'],
  ['dialogue_examples', '对话示例（表达参考，非历史）'], ['first_message', '作者开场（仅资料，未发送）'],
];
</script>

<template>
  <div data-testid="character-structured-profile" class="space-y-2 mt-3 text-sm">
    <p class="text-xs text-slate-500">独立字段资料；示例不是共同经历，开场尚未作为消息发送。字段如有矛盾，请修订源卡后新建对话。</p>
    <details v-for="[key, label] in fields.filter(([key]) => typeof profile[key] === 'string' && profile[key])" :key="key">
      <summary class="cursor-pointer text-slate-300">{{ label }}</summary>
      <p :data-testid="`character-profile-${key}`" class="mt-2 whitespace-pre-wrap break-words select-text text-slate-400">{{ profile[key] }}</p>
    </details>
  </div>
</template>
