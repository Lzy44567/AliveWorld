<script setup>
import { computed } from 'vue';
import { configStore } from '../../store/configStore';

const settings = computed(() => configStore.story.settings);
</script>

<template>
  <div class="space-y-5">
    <section class="rounded-xl border border-slate-700 bg-slate-800/30 p-4">
      <h3 class="mb-3 text-xs font-bold text-rose-300">🎲 推演与玩法</h3>
      <div class="grid grid-cols-2 gap-3">
        <label class="setting-row"><span>显示未来可能性</span><input type="checkbox" v-model="settings.showFutures"></label>
        <label class="setting-row"><span>显示命运掷骰</span><input type="checkbox" v-model="settings.showDice"></label>
        <label class="setting-row"><span>允许重掷未来</span><input type="checkbox" v-model="settings.allowReroll"></label>
        <label class="setting-row"><span>AI 行动建议</span><input type="checkbox" v-model="settings.aiSuggestions"></label>
        <label class="setting-row col-span-2"><span>启用暗流实体推演</span><input type="checkbox" v-model="settings.entitiesEnabled"></label>
      </div>
    </section>

    <section class="rounded-xl border border-slate-700 bg-slate-800/30 p-4">
      <h3 class="mb-3 text-xs font-bold text-amber-300">👾 暗流实体显示</h3>
      <div class="grid grid-cols-2 gap-3">
        <label class="setting-row"><span>显示名称</span><input type="checkbox" v-model="settings.showEntityNames"></label>
        <label class="setting-row"><span>显示动机</span><input type="checkbox" v-model="settings.showEntityMotives"></label>
        <label class="setting-row"><span>允许编辑</span><input type="checkbox" v-model="settings.allowEntityEditing"></label>
        <label class="setting-row"><span>显示气泡</span><input type="checkbox" v-model="settings.showEntityBubbles"></label>
        <label class="setting-row col-span-2"><span>显示暗流影响触发气泡（调试）</span><input type="checkbox" v-model="settings.showInfluenceBubbles"></label>
        <label class="setting-row col-span-2"><span>显示暗流因果账本（调试）</span><input type="checkbox" v-model="settings.showCausalLedger"></label>
      </div>
    </section>

    <section class="rounded-xl border border-slate-700 bg-slate-800/30 p-4">
      <h3 class="mb-3 text-xs font-bold text-cyan-300">👁️ 界面显示</h3>
      <label class="setting-row"><span>世界时间</span><input type="checkbox" v-model="settings.showTime"></label>
    </section>
  </div>
</template>

<style scoped>
.setting-row { display: flex; align-items: center; justify-content: space-between; gap: .75rem; cursor: pointer; border: 1px solid rgb(51 65 85); border-radius: .5rem; background: rgb(15 23 42 / .55); padding: .65rem .75rem; font-size: .75rem; color: rgb(203 213 225); }
.setting-row:hover { border-color: rgb(100 116 139); }
input[type="checkbox"] { width: 1rem; height: 1rem; accent-color: rgb(99 102 241); }
</style>
