<script setup>
import ExpandableTextarea from '../common/ExpandableTextarea.vue';
const model = defineModel({type:Object,required:true});
const labels = {overview:'世界概述',axioms:'公理',entries:'世界书条目',description:'设定描述',starting_scene:'登场情境',content:'内容',motive:'动机',mechanisms:'行为机制',plans:'计划',world_premise:'故事概述',opening:'故事开场',text:'创作资料',tags:'标签'};
const lines = text => text.split('\n').map(s=>s.trim()).filter(Boolean);
</script>
<template>
  <div class="space-y-3">
    <div v-for="(value,key) in model" :key="key">
      <div v-if="typeof value==='string'"><p class="mb-2 text-sm text-slate-400">{{ labels[key] || key }}</p><ExpandableTextarea v-model="model[key]" :label="labels[key] || key" :rows="3" textarea-class="bg-slate-900 p-3 rounded" /></div>
      <div v-else-if="key==='entries' && Array.isArray(value)" class="space-y-3">
        <h4>世界书条目</h4>
        <div v-for="(entry,index) in value" :key="index" class="rounded border border-slate-700 p-3 space-y-2">
          <label class="block">条目名称<input v-model="entry.name" class="ml-2 rounded bg-slate-800 p-2" /></label>
          <ExpandableTextarea v-model="entry.content" label="条目内容" :rows="3" textarea-class="bg-slate-900 p-3 rounded" />
          <label class="block text-sm">触发关键词（每行一个）<textarea :value="(entry.keywords || []).join('\n')" class="block w-full rounded bg-slate-900 p-2" @input="entry.keywords=lines($event.target.value)" /></label>
          <button class="text-xs text-rose-300" @click="value.splice(index,1)">删除条目</button>
        </div>
        <button class="text-sm text-cyan-300" @click="value.push({name:'新条目',content:'',keywords:[]})">添加条目</button>
      </div>
      <label v-else-if="Array.isArray(value)" class="block">{{ labels[key] || key }}（每行一项）<textarea :value="value.join('\n')" rows="4" class="block w-full rounded bg-slate-900 p-3" @input="model[key]=lines($event.target.value)" /></label>
    </div>
  </div>
</template>
