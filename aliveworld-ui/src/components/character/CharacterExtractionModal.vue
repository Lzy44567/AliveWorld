<script setup>
import { onMounted, ref } from 'vue';
import CharacterFieldsEditor from './CharacterFieldsEditor.vue';
import ExpandableTextarea from '../common/ExpandableTextarea.vue';
import { assetStore } from '../../store/assetStore';
const props = defineProps({ sessionId: String, sourceName: String });
const emit = defineEmits(['close']);
const profile = ref(null), name = ref(''), revision = ref(''), error = ref(''), busy = ref(false), reviewed = ref(false);
const turns = ref([]), selectedTurns = ref([]), instruction = ref(''), acknowledged = ref(false);
const experiences = ref(''), includeExperiences = ref(false), notes = ref(''), evidence = ref({});
const sourceLabel = ref(props.sourceName.startsWith('npc:') ? '故事人物' : props.sourceName);
const endpoint = `/api/v1/game/${encodeURIComponent(props.sessionId)}/character-extraction/${encodeURIComponent(props.sourceName)}`;
async function request(options, url = endpoint) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || '提取失败');
  return data;
}
onMounted(async () => {
  busy.value = true;
  try {
    const data = await request(); profile.value = data.profile; revision.value = data.revision;
    name.value = `${data.profile.name}（提取）`;
    sourceLabel.value = data.profile.name;
    const material = await request(undefined, `/api/v1/game/${encodeURIComponent(props.sessionId)}/character-material`);
    turns.value = material.turns;
  } catch (e) { error.value = e.message; }
  finally { busy.value = false; }
});
async function organize() {
  busy.value = true; error.value = '';
  try {
    const data = await request({ method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ turn_ids: selectedTurns.value, instruction: instruction.value, acknowledged: acknowledged.value }) }, `${endpoint}/organize`);
    profile.value = data.profile; revision.value = data.revision;
    experiences.value = data.experiences; notes.value = data.notes; reviewed.value = false;
    evidence.value = { evidence_turn_ids: data.evidence_turn_ids, evidence_revision: data.evidence_revision };
  } catch (e) { error.value = e.message; }
  finally { busy.value = false; }
}
async function save() {
  busy.value = true; error.value = '';
  try {
    await request({ method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.value, profile: profile.value, expected_revision: revision.value, reviewed: reviewed.value,
        include_experiences: includeExperiences.value, experiences: experiences.value, ...evidence.value }) });
    await assetStore.fetchAssets(); emit('close');
  } catch (e) { error.value = e.message; }
  finally { busy.value = false; }
}
</script>
<template>
  <Teleport to="body"><div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4">
    <section role="dialog" aria-label="提取角色卡" class="flex max-h-[90vh] w-full max-w-3xl flex-col rounded-xl border border-slate-700 bg-slate-950 text-slate-200">
      <header class="flex justify-between border-b border-slate-800 p-4"><h2>提取角色卡 · {{ sourceLabel }}</h2><button :disabled="busy" aria-label="关闭提取角色" @click="emit('close')">×</button></header>
      <div class="min-h-0 space-y-4 overflow-y-auto p-5">
        <p class="text-sm text-slate-400">保存独立全局角色卡，原故事不变。可直接编辑，也可选择公开回合交给 AI 整理。不发送幕后账本；保存前请检查不想分享的内容。</p>
        <fieldset v-if="profile" :disabled="busy" class="space-y-4">
          <details class="rounded border border-slate-700 p-3" :open="sourceName.startsWith('npc:')">
            <summary class="cursor-pointer text-indigo-300">从故事整理人设与经历 · 可选</summary>
            <div class="mt-3 max-h-64 space-y-2 overflow-y-auto">
              <label v-for="turn in turns" :key="turn.turn_id" class="block rounded bg-slate-900 p-2 text-sm">
                <input v-model="selectedTurns" type="checkbox" :value="turn.turn_id" /> 第 {{ turn.turn_id }} 回合
                <details class="mt-1"><summary class="cursor-pointer truncate text-slate-400">{{ turn.player || '故事开端' }}</summary><p class="whitespace-pre-wrap">{{ turn.player }}</p><p class="whitespace-pre-wrap">{{ turn.story }}</p></details>
              </label>
              <p v-if="!turns.length" class="text-sm text-slate-400">暂无可选公开回合，可直接填写人设。</p>
            </div>
            <ExpandableTextarea v-model="instruction" label="整理要求" placeholder="希望保留哪些特点？哪些推断需要谨慎？" :rows="2" textarea-class="mt-3 rounded border border-slate-700 bg-slate-900 p-2" />
            <label class="my-3 block text-xs text-slate-400"><input v-model="acknowledged" type="checkbox" /> 允许将选中公开回合和人物底稿发送至工坊接口，产生模型费用</label>
            <button :disabled="!acknowledged || !selectedTurns.length" class="rounded bg-indigo-800 px-3 py-2 text-sm disabled:opacity-40" @click="organize">AI 整理所选回合</button>
          </details>
          <p v-if="notes" class="whitespace-pre-wrap rounded bg-amber-950/40 p-3 text-sm text-amber-200">待审说明：{{ notes }}</p>
          <label class="block">新卡名称<input v-model="name" class="mt-2 w-full rounded border border-slate-700 bg-slate-900 p-2" /></label>
          <CharacterFieldsEditor v-if="profile.role_fields" v-model="profile.role_fields" @free-text="Object.assign(profile,$event)" />
          <template v-else><label v-for="[key,label] in [['description','人物设定'],['personality','性格'],['dialogue_examples','言行示例'],['starting_scene','开场设定']]" :key="key" class="block">{{ label }}<ExpandableTextarea v-model="profile[key]" :label="label" :rows="3" textarea-class="rounded border border-slate-700 bg-slate-900 p-2" /></label></template>
          <label class="block">外观<ExpandableTextarea v-model="profile.appearance" label="外观" :rows="3" textarea-class="rounded border border-slate-700 bg-slate-900 p-2" /></label>
          <label class="block text-sm"><input v-model="includeExperiences" type="checkbox" /> 保存旧世界经历（默认仅人设，载入时仍可忽略经历）</label>
          <ExpandableTextarea v-if="includeExperiences" v-model="experiences" label="旧世界经历" :rows="5" textarea-class="rounded border border-slate-700 bg-slate-900 p-2" />
          <label class="block text-sm"><input v-model="reviewed" type="checkbox" /> 已审阅内容，保存为独立角色卡</label>
        </fieldset>
        <p v-if="error" role="alert" class="text-sm text-rose-300">{{ error }}</p>
      </div>
      <footer class="flex justify-end gap-4 border-t border-slate-800 p-4"><button :disabled="busy" @click="emit('close')">取消</button><button :disabled="busy || !reviewed || !name.trim()" class="rounded bg-indigo-700 px-4 py-2 disabled:opacity-40" @click="save">保存到全局角色库</button></footer>
    </section>
  </div></Teleport>
</template>
