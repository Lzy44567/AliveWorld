<script setup>
import { computed } from 'vue';
import { configStore } from '../../store/configStore';
import StoryMemoryStatus from './StoryMemoryStatus.vue';

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
      <h3 class="mb-2 text-xs font-bold text-fuchsia-300">🪞 用户偏好</h3>
      <p class="mb-3 text-[10px] leading-relaxed text-slate-500">复用正文结算结果学习，不会额外发起一轮 AI 请求。候选偏好不会立刻影响故事。</p>
      <div class="grid grid-cols-2 gap-3">
        <label class="setting-row"><span>随游玩学习偏好</span><input type="checkbox" v-model="settings.learnUserPreferences"></label>
        <label class="setting-row"><span>正文参考已确认偏好</span><input type="checkbox" v-model="settings.useUserPreferences"></label>
      </div>
    </section>

    <section class="rounded-xl border border-slate-700 bg-slate-800/30 p-4">
      <h3 class="mb-2 text-xs font-bold text-indigo-300">🧠 长篇故事记忆</h3>
      <p class="mb-3 text-[10px] leading-relaxed text-slate-500">达到上下文水位后异步归档较早完整回合；永久保留原文，压缩失败不会影响正文。</p>
      <label class="setting-row"><span>自动压缩故事记忆</span><input type="checkbox" v-model="settings.autoCompressMemory"></label>
      <StoryMemoryStatus class="mt-3" />
    </section>

    <section class="rounded-xl border border-slate-700 bg-slate-800/30 p-4">
      <h3 class="mb-2 text-xs font-bold text-cyan-300">📚 世界书辅助</h3>
      <p class="mb-3 text-[10px] leading-relaxed text-slate-500">正文返回后异步识别稳定的新世界设定，不阻塞故事。动态事件不会写入世界书。</p>
      <div class="grid grid-cols-2 gap-3">
        <label class="setting-row"><span>捕获局内新设定</span><input type="checkbox" v-model="settings.worldbookCaptureEnabled"></label>
        <label class="setting-row" :class="!settings.worldbookCaptureEnabled ? 'opacity-50' : ''"><span>AI内容二次确认</span><input type="checkbox" v-model="settings.worldbookCaptureReview" :disabled="!settings.worldbookCaptureEnabled"></label>
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
