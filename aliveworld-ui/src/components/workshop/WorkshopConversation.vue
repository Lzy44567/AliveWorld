<script setup>
import { computed } from 'vue';
import { workshopStore } from '../../store/workshopStore';

const operationLabel = operation => ({
  add_entry: '新增条目', update_entry: '修改条目', deactivate_entry: '关闭条目',
  request_delete: '申请删除', update_overview: '修改概述', set_axioms: '修改公理',
  add_preference: '新增偏好', update_preference: '修改偏好',
  set_status: '改变偏好状态', delete_preference: '删除偏好',
  update_fields: '修改资产字段',
})[operation.op] || operation.op;
const operationTarget = operation =>
  operation.entry?.name || operation.entry_id || operation.preference?.statement
  || operation.preference_id || Object.keys(operation.changes || {}).join('、') || workshopStore.assetName;
const waitingText = computed(() => ({
  worldbooks: '世界书工坊正在检查设定关系与推导链……',
  characters: '角色工坊正在梳理人物目标、矛盾与表现方式……',
  styles: '文风工坊正在比较叙事规范与执行效果……',
  entities: '实体工坊正在区分动机、机制、计划与行动……',
  preferences: '偏好工坊正在分析证据、替代解释与取舍……',
})[workshopStore.type]);
</script>

<template>
  <main class="flex min-w-0 flex-1 flex-col bg-slate-950/55">
    <template v-if="workshopStore.workshopId">
      <header class="border-b border-slate-800 bg-slate-950/75 px-5 py-3">
        <div class="flex items-center justify-between gap-4">
          <div><div class="flex items-center gap-2"><h2 class="font-bold text-cyan-200">{{ workshopStore.typeInfo.icon }} {{ workshopStore.typeInfo.label }}工坊<span v-if="workshopStore.assetName"> · {{ workshopStore.assetName }}</span></h2><span v-if="workshopStore.dirty" class="text-[10px] text-amber-400">草稿已自动保存</span></div><p class="mt-1 text-[10px] text-slate-500">不推进故事时间；发布前不会改变正式资产</p></div>
          <div class="flex gap-2"><button class="rounded bg-slate-800 px-3 py-1.5 text-xs text-slate-300" @click="workshopStore.undo">撤销</button><button class="rounded bg-emerald-700 px-3 py-1.5 text-xs font-bold text-white disabled:opacity-30" :disabled="workshopStore.busy || !workshopStore.dirty" @click="workshopStore.publish">发布草稿</button></div>
        </div>
        <div class="mt-3 flex flex-wrap gap-2"><button v-for="item in workshopStore.modes" :key="item.id" class="rounded px-3 py-1 text-[10px]" :class="workshopStore.mode===item.id?'bg-cyan-800 text-white':'bg-slate-900 text-slate-500'" :title="item.description" @click="workshopStore.mode=item.id">{{ item.label }}</button></div>
        <p class="mt-2 text-[10px] leading-relaxed text-cyan-300/70">{{ workshopStore.activeMode.description }}</p>
      </header>

      <section class="min-h-0 flex-1 space-y-3 overflow-y-auto p-5 custom-scrollbar">
        <p v-if="workshopStore.activity==='loading'" class="text-sm text-slate-500">正在载入或恢复工坊草稿……</p>
        <div v-for="(message,index) in workshopStore.messages" :key="index" class="w-fit max-w-[84%] whitespace-pre-wrap rounded-xl p-3 text-sm leading-relaxed" :class="message.role==='user'?'ml-auto bg-cyan-700 text-white':'bg-slate-800 text-slate-200'">{{ message.content }}<span v-if="message.failed" class="ml-2 text-xs text-rose-200">发送失败</span></div>
        <div v-if="workshopStore.activity==='chat'" class="w-fit rounded-xl bg-slate-800 p-3 text-sm text-slate-400">{{ waitingText }}</div>
        <section v-if="workshopStore.proposed.length" class="rounded-xl border border-cyan-700/60 bg-cyan-950/25 p-3">
          <div class="flex items-center justify-between"><div><h3 class="text-xs font-bold text-cyan-300">AI 拟议修改 · 尚未写入</h3><p class="mt-1 text-[10px] text-slate-500">先审阅，再写入工坊草稿。</p></div><button class="rounded bg-cyan-700 px-3 py-1.5 text-xs font-bold text-white" @click="workshopStore.submitProposal">提交方案</button></div>
          <div v-for="operation in workshopStore.proposed" :key="operation.operation_id" class="mt-2 rounded-lg bg-black/25 p-2 text-xs text-slate-300">
            <strong class="text-cyan-200">{{ operationLabel(operation) }}</strong> · {{ operationTarget(operation) }}
            <ol v-if="operation.op==='set_axioms'" class="mt-2 list-decimal space-y-1 pl-5 text-slate-300"><li v-for="axiom in operation.axioms" :key="axiom">{{ axiom }}</li></ol>
            <p v-else-if="operation.op==='update_overview'" class="mt-2 whitespace-pre-wrap text-slate-400">{{ operation.overview }}</p>
            <p v-else-if="operation.op==='add_entry'" class="mt-2 whitespace-pre-wrap text-slate-400">{{ operation.entry?.content }}</p>
            <p v-else-if="operation.op==='update_entry'" class="mt-2 whitespace-pre-wrap text-slate-400">{{ operation.changes?.content || '将修改名称、触发词、标签或启用状态；可在左侧草稿中继续审阅。' }}</p>
            <p v-if="operation.reason" class="mt-1 text-slate-500">{{ operation.reason }}</p>
          </div>
        </section>
        <section v-if="workshopStore.pending.length" class="rounded-xl border border-amber-700/60 bg-amber-950/25 p-3">
          <h3 class="text-xs font-bold text-amber-300">需要玩家确认的高影响修改</h3>
          <div v-for="operation in workshopStore.pending" :key="operation.operation_id" class="mt-2 rounded-lg bg-black/25 p-3 text-xs text-slate-300">
            <strong>{{ operationLabel(operation) }}</strong> · {{ operationTarget(operation) }}
            <ol v-if="operation.op==='set_axioms'" class="mt-2 list-decimal space-y-1 pl-5"><li v-for="axiom in operation.axioms" :key="axiom">{{ axiom }}</li></ol>
            <p v-else-if="operation.entry?.content" class="mt-2 whitespace-pre-wrap text-slate-400">{{ operation.entry.content }}</p>
            <p v-else-if="operation.changes?.content" class="mt-2 whitespace-pre-wrap text-slate-400">{{ operation.changes.content }}</p>
            <div class="mt-2 flex gap-2"><button class="rounded bg-emerald-700 px-2 py-1" @click="workshopStore.decide(operation.operation_id,true)">接受</button><button class="rounded bg-slate-700 px-2 py-1" @click="workshopStore.decide(operation.operation_id,false)">拒绝</button></div>
          </div>
        </section>
      </section>

      <footer class="border-t border-slate-800 bg-slate-950/80 p-3">
        <div class="mb-2 flex items-center justify-between gap-3"><div class="flex rounded-lg border border-slate-700 bg-slate-900 p-0.5 text-[10px]"><button class="rounded px-2 py-1" :class="!workshopStore.commitChanges?'bg-cyan-800 text-white':'text-slate-500'" @click="workshopStore.commitChanges=false">先讨论方案</button><button class="rounded px-2 py-1" :class="workshopStore.commitChanges?'bg-emerald-800 text-white':'text-slate-500'" @click="workshopStore.commitChanges=true">允许 AI 修改草稿</button></div><span class="text-[10px] text-slate-500">{{ workshopStore.commitChanges?'低风险修改可进入草稿':'AI 只提出方案' }}</span></div>
        <div v-if="workshopStore.suggestions.length" class="mb-2 flex flex-wrap gap-1"><button v-for="item in workshopStore.suggestions" :key="item" class="rounded-full border border-cyan-800 px-2 py-1 text-[10px] text-cyan-300" @click="workshopStore.input=item">{{ item }}</button></div>
        <div class="flex gap-2"><textarea v-model="workshopStore.input" class="h-20 flex-1 rounded-lg border border-slate-700 bg-slate-900 p-3 text-sm text-slate-200" :placeholder="`${workshopStore.activeMode.description} Ctrl+Enter 发送`" @keydown.ctrl.enter.prevent="workshopStore.send()"></textarea><button class="w-20 rounded-lg bg-cyan-700 text-sm font-bold text-white disabled:opacity-40" :disabled="workshopStore.busy" @click="workshopStore.send()">{{ workshopStore.busy?'处理中':'发送' }}</button></div>
      </footer>
    </template>
    <div v-else class="flex flex-1 items-center justify-center p-8 text-center"><div><div class="text-5xl">🧰</div><h2 class="mt-4 text-lg font-bold text-cyan-200">选择一个创作对象</h2><p class="mt-2 max-w-md text-xs leading-relaxed text-slate-500">从右侧选择世界书、角色、文风或实体；偏好卡可以直接进入。工坊会复用当前主界面，但不会载入或推进故事。</p></div></div>
  </main>
</template>
