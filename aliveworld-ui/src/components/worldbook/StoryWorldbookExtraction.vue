<script setup>
import { computed, ref, watch } from 'vue';
import { gameStore } from '../../store/gameStore';
import { worldPackageApi } from '../../api/worldPackageApi';

const emit = defineEmits(['saved', 'close']);
const books = ref([]), bookId = ref(''), entryIds = ref([]), name = ref(''), revision = ref('');
const overview = ref(true), axioms = ref(true), reviewed = ref(false), busy = ref(false), error = ref('');
const loadedSession = ref('');
const book = computed(() => books.value.find(b => b.book_id === bookId.value));
let generation = 0;
async function load() {
  const epoch = ++generation, session = gameStore.sessionId;
  books.value = []; bookId.value = ''; reviewed.value = false; error.value = ''; busy.value = false;
  if (!session) { error.value = '请先载入故事，再打开提取。'; return; }
  busy.value = true;
  try {
    const data = await worldPackageApi.storyWorldbooks(session);
    if (epoch !== generation) return;
    books.value = data.books; revision.value = data.revision; loadedSession.value = session;
  } catch (e) { if (epoch === generation) error.value = e.message; }
  finally { if (epoch === generation) busy.value = false; }
}
function choose(item) {
  bookId.value = item.book_id; name.value = `${item.name}（整理版）`;
  entryIds.value = item.entries.map(e => e.id); overview.value = true; axioms.value = true; reviewed.value = false;
}
watch(() => gameStore.sessionId, load, { immediate: true });
watch([entryIds, name, overview, axioms], () => { reviewed.value = false; });
async function save() {
  if (busy.value || !reviewed.value || loadedSession.value !== gameStore.sessionId) return;
  busy.value = true; error.value = '';
  try {
    const result = await worldPackageApi.extractWorldbook(loadedSession.value, {
      book_id: bookId.value, expected_revision: revision.value, name: name.value,
      entry_ids: entryIds.value, include_overview: overview.value, include_axioms: axioms.value, reviewed: true,
    });
    emit('saved', result.asset);
  } catch (e) { error.value = e.message; }
  finally { busy.value = false; }
}
</script>

<template>
  <section role="dialog" aria-label="提取故事世界书" class="absolute inset-0 z-10 flex flex-col bg-slate-950">
    <header class="flex items-start justify-between gap-4 border-b border-slate-800 p-5">
      <div><h3 class="font-bold text-cyan-200">从当前故事提取世界书</h3><p class="mt-1 text-xs text-slate-400">{{ gameStore.currentSaveName }} · 保存独立全局副本，原故事和世界书不变；不会调用AI或上传。</p></div>
      <button :disabled="busy" aria-label="关闭提取" @click="emit('close')">×</button>
    </header>
    <div class="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
      <p class="rounded-lg bg-amber-950/40 p-3 text-xs leading-5 text-amber-200">这里只提取当前有效设定，不是原始世界。自动排除待审、停用与已撤回条目，移除来源路径和修订日志。正文仍可能含隐私或剧透，请阅读后筛选。</p>
      <div class="grid grid-cols-2 gap-2">
        <button v-for="item in books" :key="item.book_id" :disabled="busy" :aria-pressed="bookId === item.book_id" class="rounded-lg border p-3 text-left text-sm" :class="bookId === item.book_id ? 'border-cyan-500 bg-cyan-950/40' : 'border-slate-700'" @click="choose(item)">
          {{ item.name }}<small class="block text-slate-400">{{ item.entries.length }} 条可提取 · {{ item.excluded_count }} 条未纳入</small>
        </button>
      </div>
      <p v-if="!books.length && !busy" class="text-sm text-slate-400">当前故事没有启用的世界书。</p>
      <template v-if="book">
        <label class="block text-sm">新世界书名称<input v-model="name" :disabled="busy" data-testid="extraction-name" class="mt-1 w-full rounded border border-slate-700 bg-slate-900 p-2" /></label>
        <details v-if="book.overview" class="rounded border border-slate-800 p-3" open><summary><label @click.stop><input v-model="overview" :disabled="busy" type="checkbox" /> 保留概述</label></summary><p class="mt-2 whitespace-pre-wrap text-sm text-slate-300">{{ book.overview }}</p></details>
        <details v-if="book.axioms.length" class="rounded border border-slate-800 p-3" open><summary><label @click.stop><input v-model="axioms" :disabled="busy" type="checkbox" /> 保留公理</label></summary><p v-for="(text, i) in book.axioms" :key="i" class="mt-2 whitespace-pre-wrap text-sm text-slate-300">{{ i + 1 }}. {{ text }}</p></details>
        <div class="flex gap-3 text-xs text-cyan-300"><span>条目 {{ entryIds.length }}/{{ book.entries.length }}</span><button :disabled="busy" @click="entryIds = book.entries.map(e => e.id)">全选条目</button><button :disabled="busy" @click="entryIds = []">清空条目选择</button></div>
        <details v-for="entry in book.entries" :key="entry.id" class="rounded border border-slate-800 p-3">
          <summary><label @click.stop><input v-model="entryIds" :disabled="busy" type="checkbox" :value="entry.id" :aria-label="`提取 ${entry.name}`" /> {{ entry.name }}</label><span class="ml-2 text-xs text-slate-500">展开查看</span></summary>
          <p class="mt-2 text-xs text-slate-400">关键词：{{ entry.keys || '无' }} · {{ entry.tags.join('、') }}</p><p class="mt-2 whitespace-pre-wrap text-sm text-slate-300">{{ entry.content }}</p>
        </details>
      </template>
      <p v-if="error" role="alert" class="text-sm text-rose-300">{{ error }}</p>
    </div>
    <footer class="space-y-3 border-t border-slate-800 p-4">
      <label class="flex gap-2 text-xs text-slate-300"><input v-model="reviewed" :disabled="busy || !book" type="checkbox" /> 我已审阅选中内容，确认没有不希望带出的隐私或剧透</label>
      <div class="flex items-center justify-between gap-3"><button :disabled="busy" class="text-xs text-cyan-300" @click="load">刷新预览</button><span class="text-xs text-slate-500">保存后即使取消打包，副本也会保留。</span><button :disabled="busy || !book || !reviewed || !name.trim()" class="rounded bg-cyan-700 px-4 py-2 text-sm disabled:opacity-40" @click="save">{{ busy ? '处理中…' : '保存副本并加入打包' }}</button></div>
    </footer>
  </section>
</template>
