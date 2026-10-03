<script setup>
defineProps({ modelValue: String, disabled: Boolean, testId: String });
defineEmits(['update:modelValue']);
const options = [
  { value: 'messenger', title: '即时聊天', description: '像聊天消息一样交流，以角色的对白为主。', example: '「你到家了吗？我还在车站等车。」' },
  { value: 'roleplay', title: '情景扮演', description: '对白配合动作与场景旁白，不替你决定行动。', example: '她收起车票，抬头问：「你要一起等吗？」' },
];
</script>
<template>
  <fieldset :data-testid="testId" class="space-y-2 min-w-0" :disabled="disabled">
    <legend class="text-sm mb-2">表现方式</legend>
    <label v-for="option in options" :key="option.value" class="block cursor-pointer rounded-lg border p-3" :class="modelValue === option.value ? 'border-indigo-500 bg-indigo-950/40' : 'border-slate-700 bg-slate-950/40'">
      <span class="flex items-center gap-2 text-sm"><input type="radio" :name="testId" :value="option.value" :checked="modelValue===option.value" @change="$emit('update:modelValue',option.value)">{{ option.title }}</span>
      <span class="mt-1 block text-xs text-slate-400 leading-relaxed">{{ option.description }}</span>
      <span class="mt-2 block text-xs text-slate-500 leading-relaxed">{{ option.example }}</span>
    </label>
  </fieldset>
</template>
