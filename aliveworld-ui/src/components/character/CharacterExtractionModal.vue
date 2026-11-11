<script setup>
import { onMounted, ref } from 'vue';
import CharacterFieldsEditor from './CharacterFieldsEditor.vue';
import ExpandableTextarea from '../common/ExpandableTextarea.vue';
import { assetStore } from '../../store/assetStore';
const props = defineProps({ sessionId: String, sourceName: String });
const emit = defineEmits(['close']);
const profile = ref(null), name = ref(''), revision = ref(''), error = ref(''), busy = ref(false), reviewed = ref(false);
const endpoint = `/api/v1/game/${encodeURIComponent(props.sessionId)}/character-extraction/${encodeURIComponent(props.sourceName)}`;
async function request(options) {
  const response = await fetch(endpoint, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || '提取失败');
  return data;
}
onMounted(async () => {
  busy.value = true;
  try {
    const data = await request(); profile.value = data.profile; revision.value = data.revision;
    name.value = `${props.sourceName}（提取）`;
  } catch (e) { error.value = e.message; }
  finally { busy.value = false; }
});
async function save() {
  busy.value = true; error.value = '';
  try {
    await request({ method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.value, profile: profile.value, expected_revision: revision.value, reviewed: reviewed.value }) });
    await assetStore.fetchAssets(); emit('close');
  } catch (e) { error.value = e.message; }
  finally { busy.value = false; }
}
</script>
<template>
  <Teleport to="body"><div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4">
    <section role="dialog" aria-label="提取角色卡" class="flex max-h-[90vh] w-full max-w-3xl flex-col rounded-xl border border-slate-700 bg-slate-950 text-slate-200">
      <header class="flex justify-between border-b border-slate-800 p-4"><h2>提取角色卡 · {{ sourceName }}</h2><button :disabled="busy" aria-label="关闭提取角色" @click="emit('close')">×</button></header>
      <div class="min-h-0 space-y-4 overflow-y-auto p-5">
        <p class="text-sm text-slate-400">保存独立全局人设，原故事不变。本入口暂不提取游玩经历、图片或幕后账本，也不调用AI。请检查人设文字本身是否包含不想分享的内容。</p>
        <fieldset v-if="profile" :disabled="busy" class="space-y-4">
          <label class="block">新卡名称<input v-model="name" class="mt-2 w-full rounded border border-slate-700 bg-slate-900 p-2" /></label>
          <CharacterFieldsEditor v-if="profile.role_fields" v-model="profile.role_fields" @free-text="Object.assign(profile,$event)" />
          <template v-else><label v-for="[key,label] in [['description','人物设定'],['personality','性格'],['dialogue_examples','言行示例'],['starting_scene','开场设定']]" :key="key" class="block">{{ label }}<ExpandableTextarea v-model="profile[key]" :label="label" :rows="3" textarea-class="rounded border border-slate-700 bg-slate-900 p-2" /></label></template>
          <label class="block">外观<ExpandableTextarea v-model="profile.appearance" label="外观" :rows="3" textarea-class="rounded border border-slate-700 bg-slate-900 p-2" /></label>
          <label class="block text-sm"><input v-model="reviewed" type="checkbox" /> 已审阅内容，保存为独立角色卡</label>
        </fieldset>
        <p v-if="error" role="alert" class="text-sm text-rose-300">{{ error }}</p>
      </div>
      <footer class="flex justify-end gap-4 border-t border-slate-800 p-4"><button :disabled="busy" @click="emit('close')">取消</button><button :disabled="busy || !reviewed || !name.trim()" class="rounded bg-indigo-700 px-4 py-2 disabled:opacity-40" @click="save">保存到全局角色库</button></footer>
    </section>
  </div></Teleport>
</template>
