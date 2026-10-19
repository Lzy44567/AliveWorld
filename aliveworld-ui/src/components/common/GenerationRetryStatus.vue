<script setup>
import { computed, ref, watch } from 'vue';
import { generationStatus } from '../../api/generationApi';
const props = defineProps({ kind: String, identity: String, requestId: String });
const retry = ref(null), now = ref(Date.now());
const seconds = computed(() => Math.max(0, Math.ceil(((retry.value?.deadline || 0) - now.value) / 1000)));
watch(() => [props.kind, props.identity, props.requestId], ([kind, identity, requestId], _, cleanup) => {
  retry.value = null;
  if (!identity || !requestId) return;
  let disposed = false, pending = false;
  const poll = async () => {
    now.value = Date.now();
    if (pending) return;
    pending = true;
    try {
      const status = await generationStatus(kind, identity, requestId);
      if (!disposed) retry.value = status.retry ? { ...status.retry, deadline: Date.now() + status.retry.remaining_seconds * 1000 } : null;
    } catch { /* Status reads never resubmit the paid request. */ }
    finally { pending = false; }
  };
  const timer = setInterval(poll, 1000);
  cleanup(() => { disposed = true; clearInterval(timer); });
  poll();
}, { immediate: true });
</script>
<template>
  <p v-if="retry" data-testid="generation-retry-status" role="status" class="text-xs text-amber-200">
    {{ seconds ? `${seconds} 秒后重试` : '正在重试' }} · 第 {{ retry.attempt }}/{{ retry.limit }} 次额外尝试，可点击停止取消
  </p>
</template>
