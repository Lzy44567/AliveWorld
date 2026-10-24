<script setup>
import { ref, watch, nextTick } from 'vue';
import { workshopStore } from '../../store/workshopStore';
import WorkshopCreativeBrief from './WorkshopCreativeBrief.vue';
import WorldbookReferences from './WorldbookReferences.vue';
const props = defineProps({ open: Boolean });
const emit = defineEmits(['close']);
const dialog = ref(null);
watch(() => props.open, async open => {
  await nextTick();
  if (open) dialog.value.showModal();
  else dialog.value.close();
});
</script>

<template>
  <dialog ref="dialog" data-testid="workshop-settings" aria-labelledby="workshop-settings-title" class="m-auto max-h-[85vh] w-[min(36rem,calc(100vw-2rem))] overflow-y-auto rounded-xl border border-slate-700 bg-slate-950 p-5 text-slate-200 shadow-2xl backdrop:bg-black/60" @keydown.esc.stop @cancel.prevent="emit('close')" @click.self="emit('close')">
    <div class="mb-3 flex items-center justify-between"><h2 id="workshop-settings-title" class="font-bold text-cyan-200">创作设置</h2><button autofocus aria-label="关闭创作设置" class="rounded px-2 py-1 hover:bg-slate-800" @click="emit('close')">✕</button></div>
    <p class="text-xs text-slate-400">不推进故事时间；发布前不会改变正式资产。关闭窗口保留未保存的编辑。</p>
        <div class="mt-3 flex flex-wrap gap-2"><button v-for="item in workshopStore.modes" :key="item.id" class="rounded px-3 py-1 text-[10px]" :class="workshopStore.mode===item.id?'bg-cyan-800 text-white':'bg-slate-900 text-slate-500'" :title="item.description" @click="workshopStore.mode=item.id">{{ item.label }}</button></div>
        <p class="mt-2 text-[10px] leading-relaxed text-cyan-300/70">{{ workshopStore.activeMode.description }}</p>
        <WorkshopCreativeBrief />
        <WorldbookReferences />

        <details class="mb-2 text-[10px] text-slate-400" data-testid="workshop-context-settings">
          <summary class="cursor-pointer">创作记忆 · {{ workshopStore.context.useHistory ? '参考已发布讨论' : '仅参考本轮讨论' }}</summary>
          <label class="mt-2 block"><input v-model="workshopStore.context.useHistory" type="checkbox" :disabled="workshopStore.busy" /> 参考同一资产的已发布讨论</label>
          <p class="mt-1">不额外调用模型；历史原文按相关性和长度选取，会增加本次输入token，不保证召回所有细节。重要约束可写入创作目标。刷新后恢复默认设置。</p>
          <p v-if="workshopStore.type === 'preferences'" class="mt-1 text-amber-400">默认关闭。开启后会把旧偏好讨论片段发送给当前模型，其中可能包含敏感内容。</p>
          <p v-if="workshopStore.context.contextInfo" class="mt-1" data-testid="workshop-context-info">上次请求：近期 {{ workshopStore.context.contextInfo.recent_count }} 条，历史节选 {{ workshopStore.context.contextInfo.excerpt_count }} 条；可用原文共 {{ workshopStore.context.contextInfo.available_messages }} 条。</p>
        </details>
        <label class="mb-2 block text-right text-[10px] text-slate-500"><input data-testid="workshop-stream-toggle" v-model="workshopStore.streamingEnabled" type="checkbox" :disabled="workshopStore.busy" /> 流式输出</label>

  </dialog>
</template>
