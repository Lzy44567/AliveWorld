<script setup>
import { computed } from 'vue';
import { configStore } from '../../store/configStore';

const disclosureKeys = ['showEntityNames', 'showEntityMotives', 'allowEntityEditing', 'showEntityBubbles'];
const allEntityDisclosure = computed({
  get: () => disclosureKeys.every(key => configStore.settings[key]),
  set: value => disclosureKeys.forEach(key => { configStore.settings[key] = value; })
});
</script>

<template>
  <div class="col-span-2 border border-slate-700 rounded-lg p-3 space-y-3">
    <label class="flex items-center gap-2 text-sm font-bold text-purple-300 cursor-pointer">
      <input type="checkbox" v-model="configStore.settings.entitiesEnabled" class="rounded bg-slate-800 border-slate-600 text-purple-500">
      <span>新故事默认启用暗流实体推演</span>
    </label>
    <p class="text-[10px] text-slate-500">关闭后保留所有实体卡及其逐卡状态，但不会请求 Overseer；没有启用中的实体时也会自动跳过。</p>
    <div class="border-t border-slate-700 pt-3 space-y-3">
      <p class="text-sm font-bold text-amber-300">暗流实体显示（可自由组合）</p>
      <div class="grid grid-cols-2 gap-3">
        <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="allEntityDisclosure" class="rounded bg-slate-800 border-slate-600 text-amber-500"><span>实体：全部</span></label>
        <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.showEntityNames" class="rounded bg-slate-800 border-slate-600 text-amber-500"><span>显示名称</span></label>
        <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.showEntityMotives" class="rounded bg-slate-800 border-slate-600 text-amber-500"><span>显示动机</span></label>
        <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.allowEntityEditing" class="rounded bg-slate-800 border-slate-600 text-amber-500"><span>允许编辑</span></label>
        <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.showEntityBubbles" class="rounded bg-slate-800 border-slate-600 text-amber-500"><span>显示气泡</span></label>
        <label class="col-span-2 flex items-center gap-2 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.showInfluenceBubbles" class="rounded bg-slate-800 border-slate-600 text-purple-500"><span>默认显示暗流影响触发气泡（调试）</span></label>
        <label class="col-span-2 flex items-center gap-2 text-sm text-slate-300 cursor-pointer"><input type="checkbox" v-model="configStore.settings.showCausalLedger" class="rounded bg-slate-800 border-slate-600 text-purple-500"><span>默认显示暗流因果账本（调试）</span></label>
      </div>
      <p class="text-[10px] text-slate-500">显示权限不控制推演是否运行；气泡只显示获准的名称与动机。</p>
    </div>
  </div>
</template>
