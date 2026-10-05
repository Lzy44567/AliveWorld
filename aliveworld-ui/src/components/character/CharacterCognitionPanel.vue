<script setup>
import { computed, ref, watch } from 'vue';
import { cognitionRows, cognitionBasisLabels } from '../../utils/characterCognition.js';
import { memoryReasonLabels } from '../../utils/characterMemory.js';
const props = defineProps({ session:Object, report:Object, loading:Boolean, error:String, disabled:Boolean });
const emit = defineEmits(['open','source','correct']);
const basis = ref(''), object = ref(''), panel = ref(null);
watch(() => props.session.session_id, () => { basis.value=''; object.value=''; if (panel.value?.open) emit('open',true); });
const rows = computed(() => cognitionRows(props.report,props.session,basis.value,object.value));
const ready = computed(() => props.report?.revision === props.session.revision && props.report?.session_id === props.session.session_id);
const kinds = {knowledge:'认知',belief:'信念',intent:'意图',relationship:'关系',experience:'经历'};
function name(e) { return e.about_instance_id ? (props.session.participants || []).find(p => p.instance_id === e.about_instance_id)?.profile?.name || '局内参与者' : '未指定对象'; }
</script>
<template>
  <details ref="panel" data-testid="character-cognition-panel" class="mb-3 rounded bg-slate-800 p-2 text-xs text-slate-400" @toggle="emit('open',$event.target.open)">
    <summary class="cursor-pointer">本局认知索引</summary>
    <p class="mt-2">只整理当前公开账本，不是现实用户画像。角色推测不等于事实；情境和例外仍以原文为准。</p>
    <div class="mt-2 flex flex-wrap gap-1" aria-label="认知来源筛选"><button v-for="(label,key) in { '':'全部来源', ...cognitionBasisLabels }" :key="key" class="rounded px-2 py-1" :class="basis===key?'bg-indigo-800 text-white':'bg-slate-900'" :aria-pressed="basis===key" @click="basis=key">{{ label }}</button></div>
    <div class="mt-2 flex flex-wrap gap-1" aria-label="认知对象筛选"><button class="rounded px-2 py-1" :class="!object?'bg-indigo-800 text-white':'bg-slate-900'" :aria-pressed="!object" @click="object=''">全部对象</button><button v-for="p in session.participants || []" :key="p.instance_id" class="rounded px-2 py-1" :class="object===p.instance_id?'bg-indigo-800 text-white':'bg-slate-900'" :aria-pressed="object===p.instance_id" @click="object=p.instance_id">{{ p.controller==='user'?'当前用户':'当前角色' }}</button><button class="rounded px-2 py-1" :class="object==='unspecified'?'bg-indigo-800 text-white':'bg-slate-900'" :aria-pressed="object==='unspecified'" @click="object='unspecified'">未指定</button></div>
    <p v-if="loading" class="mt-2">载入中…</p><p v-else-if="error" class="mt-2 text-amber-300">{{ error }}</p><p v-else-if="!ready" class="mt-2">尚未载入当前认知</p><p v-else-if="!rows.length" class="mt-2">没有符合筛选的当前公开记录</p>
    <ul v-if="ready" class="mt-2 space-y-2"><li v-for="e in rows" :key="e.entry_id" :data-cognition-id="e.entry_id" class="rounded bg-slate-950 p-2"><p class="whitespace-pre-wrap break-words select-text text-slate-200">{{ e.content }}</p><p class="mt-1">{{ cognitionBasisLabels[e.basis] }} · {{ kinds[e.kind] }} · {{ name(e) }}</p><p v-if="e.annotation_reason" class="mt-1">{{ memoryReasonLabels[e.annotation_reason] }}（模型分类）</p><p v-if="e.supersedes_entry_id" class="mt-1">已修订此前认知；不改写过去原文。</p><div class="mt-2 flex gap-3"><button :disabled="disabled" class="underline disabled:opacity-40" @click="emit('source',e.entry_id)">查看来源</button><button :disabled="disabled" class="underline disabled:opacity-40" @click="emit('correct',session.ledger.find(item=>item.entry_id===e.entry_id))">纠正记忆</button></div></li></ul>
    <button class="mt-2 underline" :disabled="loading" @click="emit('open',true)">刷新认知</button>
  </details>
</template>
