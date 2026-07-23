<script setup>
import { computed, onMounted, ref } from 'vue';
import { preferenceApi } from '../../api/preferenceApi';
import { uiStore } from '../../store/uiStore';
import { gameStore } from '../../store/gameStore';
import { preferenceStore } from '../../store/preferenceStore';
import InlineDeleteConfirm from '../common/InlineDeleteConfirm.vue';
import { useDeleteConfirmation } from '../../composables/useDeleteConfirmation';

const loading = ref(false);
const preferences = ref([]);
const editingId = ref('');
const editingText = ref('');
const declarationText = ref('');
const declarationCategory = ref('story');
const declarationPolarity = ref('prefer');
const declarationSensitive = ref(false);
const analyzing = ref(false);
const { confirmDeleteId, requestDelete, cancelDelete } = useDeleteConfirmation();
const openWorkshop = () => {
  uiStore.modals.settings = false;
  uiStore.modals.preferenceWorkshop = true;
};
const categoryLabels = {
  story: '剧情发展', narrative: '剧情发展', adult: '色情内容', action: '动作描写',
  character: '角色偏好', relationship: '关系互动', visual: '视觉', content: '内容', boundary: '边界', other: '其他'
};
const active = computed(() => preferences.value.filter(item => item.status === 'active'));
const candidates = computed(() => preferences.value.filter(item => item.status === 'candidate'));
const disabled = computed(() => preferences.value.filter(item => item.status === 'disabled'));
const recentEvidence = computed(() => [...preferenceStore.evidence].reverse().slice(0, 30));
const evidenceById = computed(() => Object.fromEntries(preferenceStore.evidence.map(item => [item.id, item])));
const signalLabels = {
  choice: '故事选择', reroll: '重掷未来', retry: '重试回合', undo: '撤回回合',
  generation: '生成/重生成图片', declaration: '明确声明', other: '其他'
};
const directionLabels = { support: '支持', against: '反对', neutral: '中性' };
const strengthLabels = { weak: '弱', moderate: '中', strong: '强' };

async function refresh() {
  loading.value = true;
  try {
    const data = await preferenceStore.refresh();
    preferences.value = data.preferences || [];
  } catch (error) {
    uiStore.showToast(error.message, 'error');
  } finally {
    loading.value = false;
  }
}

async function declarePreference() {
  const text = declarationText.value.trim();
  if (!text) return;
  try {
    await preferenceApi.declare(text, gameStore.sessionId || '', {
      category: declarationCategory.value,
      polarity: declarationPolarity.value,
      sensitive: declarationSensitive.value
    });
    declarationText.value = '';
    await refresh();
    uiStore.showToast('已作为高先验偏好保存，后续证据仍可完善它');
  } catch (error) {
    uiStore.showToast(error.message, 'error');
  }
}

async function analyzeNow() {
  if (!gameStore.sessionId) return uiStore.showToast('请先载入一个故事', 'error');
  analyzing.value = true;
  try {
    const result = await preferenceApi.analyze(gameStore.sessionId, true);
    await refresh();
    uiStore.showToast(result.changed?.length ? `分析完成，更新 ${result.changed.length} 个假设` : (result.skipped || '分析完成'));
  } catch (error) {
    uiStore.showToast(error.message, 'error');
  } finally {
    analyzing.value = false;
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
      <div class="flex items-center justify-between gap-3">
        <h3 class="text-sm font-bold text-fuchsia-300">🪞 用户偏好卡</h3>
        <button class="rounded-lg border border-fuchsia-700/60 bg-fuchsia-950/40 px-3 py-1.5 text-xs font-bold text-fuchsia-200 hover:bg-fuchsia-900/50" @click="openWorkshop">进入偏好工坊</button>
      </div>
      <p class="mt-1 text-[11px] leading-relaxed text-slate-400">
        AliveWorld 会随游玩积累有依据的偏好信号。直接表达的偏好可立即生效；普通行为通常要重复出现才会激活。
        角色扮演行为不应被当成玩家本人偏好。
      </p>
    </section>

    <section class="rounded-xl border border-fuchsia-900/60 bg-fuchsia-950/20 p-3">
      <label class="text-xs font-bold text-fuchsia-200">先随手写一点</label>
      <p class="mt-1 text-[10px] text-slate-500">这会成为高先验方向，不是不可修改的绝对规则。</p>
      <textarea v-model="declarationText" class="mt-2 h-20 w-full resize-none rounded-lg border border-slate-700 bg-slate-950 p-2 text-xs text-slate-200 outline-none focus:border-fuchsia-600" placeholder="例如：我喜欢角色展示力量后引起周围人的反应，但不希望每次都这样写。"></textarea>
      <div class="mt-2 grid grid-cols-2 gap-2 md:grid-cols-3">
        <select v-model="declarationCategory" class="edit-input">
          <option v-for="(label, key) in categoryLabels" :key="key" :value="key">{{ label }}</option>
        </select>
        <select v-model="declarationPolarity" class="edit-input"><option value="prefer">希望出现</option><option value="avoid">希望回避</option></select>
        <label class="flex items-center gap-2 rounded-lg border border-slate-700 px-2 text-[11px] text-slate-400"><input v-model="declarationSensitive" type="checkbox">敏感内容</label>
      </div>
      <div class="mt-2 flex items-center justify-between gap-2">
        <span class="text-[10px] text-slate-500">待分析行为证据：{{ preferenceStore.pendingEvidenceCount }}</span>
        <div class="flex gap-2">
          <button class="mini-btn" :disabled="analyzing || !gameStore.sessionId" @click="analyzeNow">{{ analyzing ? '分析中…' : '重新分析证据' }}</button>
          <button class="mini-btn text-fuchsia-200" @click="declarePreference">保存初始方向</button>
        </div>
      </div>
    </section>

    <section v-if="preferenceStore.analysis.coverage_note" class="rounded-lg border border-amber-900/50 bg-amber-950/10 p-3 text-[10px] leading-relaxed text-amber-100/80">
      <strong>本轮分析边界：</strong>{{ preferenceStore.analysis.coverage_note }}
      <ul v-if="preferenceStore.analysis.missing_possibilities?.length" class="mt-1 list-disc pl-4 text-slate-400">
        <li v-for="item in preferenceStore.analysis.missing_possibilities" :key="item">{{ item }}</li>
      </ul>
    </section>

    <details class="rounded-xl border border-slate-700 bg-slate-950/30">
      <summary class="flex cursor-pointer list-none items-center justify-between px-3 py-2 text-xs font-bold text-sky-300">
        <span>🔎 偏好证据时间线</span>
        <span class="text-[10px] font-normal text-slate-500">最近 {{ recentEvidence.length }} 条</span>
      </summary>
      <div class="space-y-2 border-t border-slate-700 p-3">
        <p class="text-[10px] leading-relaxed text-slate-500">这里显示系统实际记录了什么，不代表已经认定你的心理原因。重掷、撤回、重试和重新生图始终只是弱证据。</p>
        <article v-for="item in recentEvidence" :key="item.id" class="rounded-lg border border-slate-800 bg-slate-950/70 p-2">
          <div class="flex flex-wrap items-center gap-2 text-[9px] text-slate-500">
            <span class="tag">{{ signalLabels[item.signal_type] || item.signal_type }}</span>
            <span>{{ item.save_name || '全局' }}</span>
            <span>{{ item.analyzed ? '已分析' : '待分析' }}</span>
            <span>{{ item.source === 'interaction' ? '界面行为' : '正文证据' }}</span>
          </div>
          <p class="mt-1 text-[11px] leading-relaxed text-slate-300">{{ item.summary }}</p>
          <details v-if="item.context" class="mt-1 text-[10px] text-slate-500"><summary class="cursor-pointer">查看最小情境</summary><p class="mt-1 whitespace-pre-wrap">{{ item.context }}</p></details>
        </article>
        <p v-if="!recentEvidence.length" class="py-3 text-center text-xs text-slate-600">还没有记录到偏好证据。</p>
      </div>
    </details>

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
            <details v-if="item.assessments?.length" class="mt-2 text-[10px] text-slate-500">
              <summary class="cursor-pointer">查看 Python 后验依据</summary>
              <div class="mt-1 space-y-1 border-l border-emerald-900/60 pl-2">
                <p v-for="assessment in item.assessments" :key="`${item.id}:${assessment.evidence_id}`">
                  {{ directionLabels[assessment.direction] || assessment.direction }} ·
                  {{ strengthLabels[assessment.strength] || assessment.strength }}证据：
                  {{ evidenceById[assessment.evidence_id]?.summary || assessment.evidence_id }}
                  <span v-if="assessment.reason">（{{ assessment.reason }}）</span>
                </p>
              </div>
            </details>
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
        <details v-if="item.assessments?.length" class="mt-2 text-[10px] text-slate-500">
          <summary class="cursor-pointer">查看证据与强度</summary>
          <p v-for="assessment in item.assessments" :key="`${item.id}:${assessment.evidence_id}`" class="mt-1">
            {{ directionLabels[assessment.direction] || assessment.direction }} ·
            {{ strengthLabels[assessment.strength] || assessment.strength }}：
            {{ evidenceById[assessment.evidence_id]?.summary || assessment.evidence_id }}
          </p>
        </details>
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
