<script setup>
import { computed, ref, watch } from 'vue';
const props = defineProps({ session: Object, contact: Object, loading: Boolean, error: String, disabled: Boolean, quotaBusy: Boolean });
const emit = defineEmits(['refresh', 'update', 'quota']);
const minutes = ref(10), maximum = ref(2), calls = ref(5), contacts = ref(10);
const settings = computed(() => props.contact?.settings);
const quota = computed(() => props.contact?.quota);
const supported = computed(() => props.session?.schema_version === 2 && !props.session.schema_read_only);
const stateText = computed(() => ({ idle: '等待下一条正式玩家消息开始周期', armed: '等待完整闲置时间', planning: '正在规划本周期联系', planned: '已规划，等待送达', exhausted: '本周期已结束，等待下一条玩家消息' }[props.contact?.state] || '状态待核对'));
const localTime = value => value ? new Date(value).toLocaleString() : '';
watch(settings, value => { if (value) { minutes.value = value.idle_seconds / 60; maximum.value = value.max_contacts; } }, { immediate: true });
watch(quota, value => { if (value) { calls.value = value.call_limit; contacts.value = value.contact_limit; } }, { immediate: true });
function enable(event) {
  if (event.target.checked && !window.confirm('开启主动联系会额外调用所选模型并产生费用。每日次数上限不等于精确金额或 token 预算；仅本地服务运行时可联系。下一条正式玩家消息才开始新周期。确定仅为当前会话开启？')) { event.target.checked = false; return; }
  emit('update', { enabled: event.target.checked });
}
</script>
<template>
  <details data-testid="character-proactive-panel" class="mt-4 text-sm" @toggle="$event.target.open && supported && emit('refresh')">
    <summary class="cursor-pointer">主动联系 · {{ settings?.enabled ? settings.paused ? '已暂停' : '已开启' : '默认关闭' }}</summary>
    <p v-if="!supported" class="mt-2 text-xs text-amber-200" data-testid="character-proactive-unsupported">旧格式会话需新建或显式升级后才能开启；不会自动转换此对话。</p>
    <div v-else class="mt-3 space-y-3">
      <p class="text-xs text-slate-400">额外模型调用可能收费；次数限制不等于精确金额或 token 预算。仅本地服务运行时联系；开启或恢复后，下一条正式玩家消息才开始周期。</p>
      <p v-if="loading && !contact" class="text-xs text-slate-500">读取设置中…</p>
      <label class="flex items-center justify-between gap-2">允许当前会话主动联系<input data-testid="character-proactive-enabled" type="checkbox" role="switch" :checked="settings?.enabled || false" :disabled="disabled || !settings" @change="enable"></label>
      <template v-if="settings">
        <form class="space-y-2" @submit.prevent="emit('update', { idle_seconds: Math.round(Number(minutes)*60), max_contacts: Number(maximum) })">
          <label class="block text-xs">连续闲置分钟<input v-model="minutes" data-testid="character-proactive-idle" type="number" min="1" max="120" step="1" required class="field" :disabled="disabled"></label>
          <label class="block text-xs">每周期最多联系组<input v-model="maximum" data-testid="character-proactive-max" type="number" min="1" max="5" step="1" required class="field" :disabled="disabled"></label>
          <button data-testid="character-proactive-save" class="text-xs underline text-indigo-200" :disabled="disabled">保存当前会话设置</button>
        </form>
        <button v-if="settings.enabled" data-testid="character-proactive-pause" class="text-xs underline text-amber-200" :disabled="disabled" @click="emit('update', { paused: !settings.paused })">{{ settings.paused ? '恢复（等待新消息）' : '暂停主动联系' }}</button>
        <p data-testid="character-proactive-state" class="text-xs text-slate-400">{{ settings.paused ? '已暂停，未送达计划已取消' : !settings.enabled ? '已关闭，不会规划主动联系' : stateText }}</p>
        <p v-if="contact.next_due_at" class="text-xs text-slate-500">下次计划时间：{{ localTime(contact.next_due_at) }}</p>
      </template>
      <p v-if="contact?.warning" class="text-xs text-amber-200">主动联系暂不可执行：{{ contact.warning }}</p>
      <details v-if="quota" class="text-xs">
        <summary class="cursor-pointer">全局每日次数限额</summary>
        <p class="mt-2 text-slate-400" data-testid="character-proactive-quota">规划调用 {{ quota.calls_used }}/{{ quota.call_limit }}；联系组占用 {{ quota.contacts_used }}/{{ quota.contact_limit }}。全部会话共用，正常聊天不计入。</p>
        <p class="mt-1 text-slate-500">固定 UTC 预算日；本地重置时间：{{ localTime(quota.resets_at) }}。已预占但取消的调用仍计数。</p>
        <form class="mt-2 space-y-2" @submit.prevent="emit('quota', { call_limit: Number(calls), contact_limit: Number(contacts) })">
          <label class="block">每日规划调用上限<input v-model="calls" data-testid="character-contact-call-limit" type="number" min="1" max="100" step="1" required class="field" :disabled="quotaBusy"></label>
          <label class="block">每日联系组上限<input v-model="contacts" data-testid="character-contact-limit" type="number" min="1" max="100" step="1" required class="field" :disabled="quotaBusy"></label>
          <button data-testid="character-contact-quota-save" class="underline text-indigo-200" :disabled="quotaBusy">保存全局每日限额</button>
        </form>
      </details>
      <p v-if="error" data-testid="character-proactive-error" class="text-xs text-rose-300">{{ error }}</p>
      <button class="text-xs underline text-slate-400" :disabled="loading" @click="emit('refresh')">刷新主动联系状态</button>
    </div>
  </details>
</template>
<style scoped>
.field { display:block; width:100%; margin-top:.35rem; padding:.4rem; border:1px solid #334155; border-radius:.5rem; background:#020617; color:#e2e8f0; }
button:disabled { opacity:.4; cursor:not-allowed; }
</style>
