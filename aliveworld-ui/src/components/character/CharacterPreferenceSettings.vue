<script setup>
const props = defineProps({ settings: { type: Object, default: () => ({ enabled: false, include_sensitive: false }) }, disabled: Boolean });
const emit = defineEmits(['update']);
function enable(event) {
  const enabled = event.target.checked;
  event.target.checked = props.settings.enabled === true;
  emit('update', { enabled, include_sensitive: enabled && props.settings.include_sensitive === true });
}
function sensitive(event) {
  const include_sensitive = event.target.checked;
  event.target.checked = props.settings.include_sensitive === true;
  emit('update', { enabled: true, include_sensitive });
}
</script>
<template>
  <div class="mt-5 text-sm" data-testid="character-preference-settings">
    <label class="flex items-center justify-between gap-3">启用用户偏好卡<input data-testid="character-preferences-enabled" type="checkbox" role="switch" :checked="settings.enabled" :disabled="disabled" @change="enable"></label>
    <p class="mt-1 text-xs text-slate-500">仅参考已确认偏好及全局分类开关，不分析私聊。偏好不能覆盖角色人设或你的选择。</p>
    <template v-if="settings.enabled">
      <label class="mt-3 flex items-center justify-between gap-3">允许参考敏感偏好<input data-testid="character-preferences-sensitive" type="checkbox" role="switch" :checked="settings.include_sensitive" :disabled="disabled" @change="sensitive"></label>
      <p class="mt-1 text-xs text-slate-500">开启后可向本会话的模型发送已标记敏感或成人类的确认偏好。未标记的隐私文本无法自动识别，请先正确分类。</p>
    </template>
    <p class="mt-2 text-[11px] text-slate-500">设置保存在此会话。每次请求开始时取材，预算不足时整条省略；重试与重生成重新读取当前授权和偏好，不保留偏好副本。</p>
  </div>
</template>
