<script setup>
import { computed, ref } from 'vue';
import ExpandableTextarea from '../common/ExpandableTextarea.vue';
import { roleFieldSpecs, structuredDraft, compatibleRoleText, roleFieldsError } from '../../utils/characterFields.js';
const props = defineProps({ description: { type: String, default: '' }, scene: { type: String, default: '' } });
const model = defineModel();
const emit = defineEmits(['free-text']);
const conversion = ref(null);
const error = computed(() => roleFieldsError(conversion.value || model.value));
function downgrade() {
  if (!window.confirm('转为自由文本将失去独立示例语义，保留合并描述与卡片开场为草稿；保存后才生效。继续？')) return;
  emit('free-text', { description: compatibleRoleText(model.value), starting_scene: model.value.first_message });
  model.value = null;
}
</script>
<template>
  <section data-testid="character-fields-editor" class="space-y-3">
    <template v-if="model || conversion">
      <div class="rounded-lg border border-indigo-800 p-3 text-xs text-indigo-200">
        <p v-if="conversion">启用预览：原描述→背景与外观，原登场情境→初始情景；性格、示例和卡片开场默认为空。可先调整下方分配。取消不会改动原草稿。</p>
        <p v-else>独立字段编辑：示例是表达参考，不是共同经历；卡片开场仅供创建对话时主动采用，既有会话快照不变。</p>
      </div>
      <label v-for="[key,label,limit] in roleFieldSpecs" :key="key" class="block text-xs text-slate-300">
        {{ label }} <span class="text-slate-500">{{ Array.from((conversion || model)[key] || '').length }} / {{ limit }}</span>
        <ExpandableTextarea v-model="(conversion || model)[key]" :data-testid="`role-field-${key}`" :label="label" :rows="key==='dialogue_examples'?6:3" :placeholder="key==='dialogue_examples'?'情景：…\n行为：…\n对白：…':''" textarea-class="mt-2 rounded border border-slate-700 bg-slate-950 p-3 text-sm" />
      </label>
      <p v-if="error" class="text-xs text-rose-300">{{ error }}</p>
      <div v-if="conversion" class="flex gap-3 text-xs"><button type="button" data-testid="role-fields-confirm" :disabled="Boolean(error)" class="rounded bg-indigo-700 px-3 py-2 disabled:opacity-40" @click="model=conversion; conversion=null">采用此分配</button><button type="button" data-testid="role-fields-cancel" @click="conversion=null">取消启用</button></div>
      <button v-else type="button" data-testid="asset-convert-free-text" class="text-xs text-slate-400 underline" @click="downgrade">转为自由文本编辑</button>
    </template>
    <button v-else type="button" data-testid="role-fields-enable" class="rounded border border-indigo-600 px-3 py-2 text-xs text-indigo-200" @click="conversion=structuredDraft(description,scene)">启用独立字段与示例</button>
  </section>
</template>
