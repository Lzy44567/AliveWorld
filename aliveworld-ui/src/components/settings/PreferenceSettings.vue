<script setup>
import { computed, onMounted, ref } from 'vue';
import { preferenceApi } from '../../api/preferenceApi';
import { uiStore } from '../../store/uiStore';
import InlineDeleteConfirm from '../common/InlineDeleteConfirm.vue';
import { useDeleteConfirmation } from '../../composables/useDeleteConfirmation';

const loading = ref(false);
const preferences = ref([]);
const editingId = ref('');
const editingText = ref('');
const { confirmDeleteId, requestDelete, cancelDelete } = useDeleteConfirmation();
const categoryLabels = {
  narrative: '叙事', character: '角色', relationship: '关系', visual: '视觉',
  content: '内容', boundary: '边界', other: '其他'
};
const active = computed(() => preferences.value.filter(item => item.status === 'active'));
const candidates = computed(() => preferences.value.filter(item => item.status === 'candidate'));
const disabled = computed(() => preferences.value.filter(item => item.status === 'disabled'));

async function refresh() {
  loading.value = true;
  try {
    const data = await preferenceApi.list();
    preferences.value = data.preferences || [];
  } catch (error) {
    uiStore.showToast(error.message, 'error');
  } finally {
    loading.value = false;
  }
}

async function update(item, updates, message = '偏好已更新') {
  try {
    await preferenceApi.update(item.id, updates);
    editingId.value = '';
    await refresh();
    uiStore.showToast(message);
  } catch (error) {
    uiStore.showToast(error.message, 'error');
  }
}

function beginEdit(item) {
  editingId.value = item.id;
  editingText.value = item.statement;
}

async function remove(item) {
  try {
    await preferenceApi.remove(item.id);
    cancelDelete();
    await refresh();
    uiStore.showToast('偏好及其学习证据已删除');
  } catch (error) {
    uiStore.showToast(error.message, 'error');
  }
}

onMounted(refresh);
</script>

<template>
  <div class="space-y-5">
    <section>
      <h3 class="text-sm font-bold text-fuchsia-300">🪞 用户偏好卡</h3>
      <p class="mt-1 text-[11px] leading-relaxed text-slate-400">
        AliveWorld 会随游玩积累有依据的偏好信号。直接表达的偏好可立即生效；普通行为通常要重复出现才会激活。
        角色扮演行为不应被当成玩家本人偏好。
      </p>
    </section>

    <p v-if="loading" class="text-xs text-slate-500">正在读取偏好卡……</p>

    <section v-if="active.length" class="space-y-2">
      <h4 class="text-xs font-bold text-emerald-300">已生效</h4>
      <article v-for="item in active" :key="item.id" class="preference-card border-emerald-900/70">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <div class="mb-1 flex flex-wrap items-center gap-2 text-[10px]">
              <span class="tag">{{ categoryLabels[item.category] || '其他' }}</span>
              <span :class="item.polarity === 'avoid' ? 'text-rose-300' : 'text-emerald-300'">{{ item.polarity === 'avoid' ? '希望回避' : '偏好' }}</span>
              <span class="text-slate-500">证据 {{ item.evidence_count }} · 可信度 {{ Math.round(item.confidence * 100) }}%</span>
            </div>
            <input v-if="editingId === item.id" v-model="editingText" class="edit-input" @keyup.enter="update(item, { statement: editingText })">
            <p v-else class="text-xs leading-relaxed text-slate-200">{{ item.statement }}</p>
          </div>
          <div class="flex shrink-0 gap-1">
            <button v-if="editingId !== item.id" class="mini-btn" @click="beginEdit(item)">修正</button>
            <button v-else class="mini-btn text-emerald-300" @click="update(item, { statement: editingText })">保存</button>
            <button class="mini-btn" @click="update(item, { status: 'disabled' }, '偏好已停用')">停用</button>
            <InlineDeleteConfirm compact :active="confirmDeleteId === item.id" :confirm-id="item.id" @request="requestDelete(item.id)" @cancel="cancelDelete" @confirm="remove(item)" />
          </div>
        </div>
      </article>
    </section>

    <section v-if="candidates.length" class="space-y-2">
      <h4 class="text-xs font-bold text-amber-300">学习中的候选</h4>
      <p class="text-[10px] text-slate-500">候选不会影响正文；再次得到可靠证据后可自动生效，也可以提前确认或丢弃。</p>
      <article v-for="item in candidates" :key="item.id" class="preference-card border-amber-900/60">
        <p class="text-xs text-slate-200">{{ item.statement }}</p>
        <p class="mt-1 text-[10px] text-slate-500">{{ categoryLabels[item.category] || '其他' }} · 证据 {{ item.evidence_count }} · {{ Math.round(item.confidence * 100) }}%</p>
        <div class="mt-2 flex gap-2">
          <button class="mini-btn text-emerald-300" @click="update(item, { status: 'active' }, '候选已确认')">确认偏好</button>
          <InlineDeleteConfirm compact :active="confirmDeleteId === item.id" :confirm-id="item.id" @request="requestDelete(item.id)" @cancel="cancelDelete" @confirm="remove(item)" />
        </div>
      </article>
    </section>

    <section v-if="disabled.length" class="space-y-2">
      <h4 class="text-xs font-bold text-slate-400">已停用</h4>
      <article v-for="item in disabled" :key="item.id" class="preference-card opacity-70">
        <div class="flex items-center justify-between gap-3">
          <p class="text-xs text-slate-300">{{ item.statement }}</p>
          <button class="mini-btn" @click="update(item, { status: 'active' }, '偏好已重新启用')">重新启用</button>
        </div>
      </article>
    </section>

    <div v-if="!loading && !preferences.length" class="rounded-lg border border-dashed border-slate-700 p-5 text-center text-xs text-slate-500">
      暂无偏好记录。继续游玩即可逐步形成，不需要先填写表格。
    </div>
  </div>
</template>

<style scoped>
.preference-card { border-width: 1px; border-radius: .75rem; background: rgb(15 23 42 / .6); padding: .75rem; }
.tag { border: 1px solid rgb(71 85 105); border-radius: .35rem; padding: .1rem .35rem; color: rgb(148 163 184); }
.mini-btn { border-radius: .4rem; background: rgb(51 65 85 / .8); padding: .3rem .5rem; font-size: .65rem; color: rgb(203 213 225); }
.mini-btn:hover { background: rgb(71 85 105); }
.edit-input { width: 100%; border: 1px solid rgb(99 102 241); border-radius: .4rem; background: rgb(2 6 23); padding: .45rem .55rem; font-size: .75rem; color: white; outline: none; }
</style>
