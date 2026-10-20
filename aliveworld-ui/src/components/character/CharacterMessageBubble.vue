<script setup>
import { computed, onUnmounted, ref } from 'vue';
const props = defineProps({ row: Object, userId: String, userName: String, aiName: String, actions: { type: Object, default: () => ({}) } });
const emit = defineEmits(['action']);
const menu = ref(false);
const menuPosition = ref({});
const actionable = computed(() => Object.values(props.actions).some(Boolean));
let hold;
function placeMenu(element) {
  const rect=element.getBoundingClientRect();
  menuPosition.value={left:`${Math.max(8,Math.min(innerWidth-216,rect.right-208))}px`,top:`${Math.max(8,Math.min(innerHeight-190,rect.bottom+4))}px`};
  menu.value=true;
}
function openMenu(event) { if (!actionable.value) return; event.preventDefault(); placeMenu(event.currentTarget); }
function toggleMenu(event) { if (menu.value) menu.value=false; else placeMenu(event.currentTarget); }
function cancelHold() { clearTimeout(hold); }
function startHold(event) { if (event.pointerType === 'mouse' || !actionable.value) return; const element=event.currentTarget; hold = setTimeout(() => placeMenu(element), 500); }
function act(name) { menu.value = false; emit('action', name); }
onUnmounted(cancelHold);
const own = computed(() => props.row.message.speaker_instance_id === props.userId);
const name = computed(() => own.value ? props.userName || '我' : props.aiName || '角色');
</script>
<template>
  <div data-testid="character-message-row" :data-message-id="row.key" :data-temporary="row.temporary" class="space-y-2">
    <details v-if="row.ooc_note" data-testid="character-turn-ooc" class="text-xs text-slate-400 border border-slate-800 rounded-lg px-3 py-2">
      <summary class="cursor-pointer">本次场外提示（非角色台词）</summary>
      <p class="whitespace-pre-wrap break-words select-text mt-2">{{ row.ooc_note }}</p>
    </details>
    <div class="flex items-start gap-2 md:gap-3" :class="own ? 'flex-row-reverse' : ''">
      <span aria-hidden="true" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-sm" :class="own ? 'bg-indigo-800' : 'bg-slate-700'">{{ Array.from(name)[0] }}</span>
      <div class="min-w-0 max-w-[calc(100%_-_3rem)] md:max-w-[72%] relative" @keydown.esc="menu=false" @focusout="event => { if (!event.currentTarget.contains(event.relatedTarget)) menu=false; }">
        <p class="mb-1 text-[11px] text-slate-500" :class="own ? 'text-right' : ''">{{ name }}<span v-if="row.origin==='proactive'" data-testid="character-proactive-label" class="ml-2 text-indigo-300">主动联系</span><span v-if="row.temporary" class="ml-2" title="回复正在生成，完成后保存" aria-label="回复生成中，尚未保存">◌</span></p>
        <!-- Text updates in this same keyed bubble. Confirmation does not replay an animation. -->
        <p :data-testid="own ? 'character-user-message' : 'character-ai-message'" class="rounded-xl px-4 py-3 whitespace-pre-wrap break-words select-text leading-relaxed" :class="own ? 'rounded-tr-sm bg-indigo-700/70' : 'rounded-tl-sm bg-slate-800'" @contextmenu="openMenu" @pointerdown="startHold" @pointerup="cancelHold" @pointermove="cancelHold" @pointercancel="cancelHold">{{ row.message.content }}<span v-if="row.temporary && !row.ended" aria-hidden="true" class="inline-block ml-1 h-3 w-px bg-slate-400"></span></p>
        <div v-if="actionable" class="flex items-center gap-2 mt-1" :class="own ? 'justify-end' : ''">
          <button v-if="actions.failed" data-testid="character-message-failed" class="rounded-full bg-rose-600 text-white w-5 h-5 text-xs" :title="actions.retry ? '消息已发送，回复未完成。点击重试回复' : '消息已发送，回复未完成。查看操作'" :aria-label="actions.retry ? '回复未完成，重试回复' : '回复未完成，查看操作'" @click="actions.retry ? act('retry') : toggleMenu($event)">!</button>
          <button aria-label="消息操作" :aria-expanded="menu" class="text-slate-500 hover:text-slate-200 px-2 text-sm" @click="toggleMenu">···</button>
        </div>
        <div v-if="menu && actionable" role="menu" aria-label="整批消息操作" :style="menuPosition" class="fixed z-50 w-52 rounded-lg border border-slate-600 bg-slate-800 shadow-xl p-1 text-sm">
          <button v-if="actions.retry" role="menuitem" class="block w-full text-left px-3 py-2 hover:bg-slate-700" @click="act('retry')">重试回复</button>
          <button v-if="actions.edit" role="menuitem" data-testid="character-edit-failed" class="block w-full text-left px-3 py-2 hover:bg-slate-700" @click="act('edit')">撤回并修改本批消息</button>
          <button v-if="actions.regenerate" role="menuitem" class="block w-full text-left px-3 py-2 hover:bg-slate-700" @click="act('regenerate')">重新生成本批回复</button>
          <button v-if="actions.undo" role="menuitem" class="block w-full text-left px-3 py-2 hover:bg-slate-700" @click="act('undo')">撤回本批消息与回复</button>
          <button role="menuitem" class="block w-full text-left px-3 py-2 text-slate-400" @click="menu=false">关闭菜单</button>
        </div>
      </div>
    </div>
  </div>
</template>
