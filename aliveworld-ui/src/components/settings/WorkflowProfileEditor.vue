<script setup>
import { computed, reactive, ref, watch } from 'vue';
import { imageApi } from '../../api/imageApi';
import { uiStore } from '../../store/uiStore';

const props = defineProps({ workflowId: { type: String, required: true } });
const emit = defineEmits(['loaded']);
const loading = ref(false);
const saving = ref(false);
const detail = ref(null);
const form = reactive({ allow_overrides:false, overrides:{}, mapping_overrides:{}, player_positive:'', player_negative:'' });
const labels = {
  positive:'正向提示词', negative:'负向提示词', width:'宽度', height:'高度', batch_size:'生成张数',
  checkpoint:'生图模型', seed:'随机种子', steps:'迭代步数', cfg:'CFG', filename_prefix:'输出文件名'
};
const editable = ['checkpoint','width','height','batch_size','seed','steps','cfg'];
const reportItems = computed(() => detail.value?.mapping_report?.parameters || []);
const mappedOverrides = computed(() => reportItems.value.filter(item => item.mapped && editable.includes(item.key)));
const previewPositive = computed(() => [detail.value?.defaults?.positive, '〈AI 场景提示词〉', form.player_positive].filter(Boolean).join(', '));
const previewNegative = computed(() => [detail.value?.defaults?.negative, '〈AI 本次负面词〉', form.player_negative].filter(Boolean).join(', '));

const copyForm = profile => {
  form.allow_overrides = Boolean(profile?.allow_overrides);
  form.overrides = { ...(profile?.overrides || {}) };
  form.mapping_overrides = { ...(profile?.mapping_overrides || {}) };
  form.player_positive = profile?.player_positive || '';
  form.player_negative = profile?.player_negative || '';
};
const setMapping = (key, raw) => {
  const next = { ...form.mapping_overrides };
  if (!raw) delete next[key];
  else next[key] = JSON.parse(raw);
  form.mapping_overrides = next;
};
const load = async () => {
  if (!props.workflowId) return;
  loading.value = true;
  try {
    detail.value = await imageApi.getWorkflow(props.workflowId);
    copyForm(detail.value.profile);
    emit('loaded', detail.value);
  } catch (error) { uiStore.showToast(error.message, 'error'); }
  finally { loading.value = false; }
};
const save = async () => {
  saving.value = true;
  try {
    const profile = await imageApi.saveWorkflowProfile(props.workflowId, form);
    copyForm(profile);
    await load();
    uiStore.showToast('工作流配置档案已保存');
  } catch (error) { uiStore.showToast(error.message, 'error'); }
  finally { saving.value = false; }
};
const reset = async () => {
  try {
    const profile = await imageApi.resetWorkflowProfile(props.workflowId);
    copyForm(profile);
    await load();
    uiStore.showToast('已恢复工作流原值');
  } catch (error) { uiStore.showToast(error.message, 'error'); }
};
watch(() => props.workflowId, load, { immediate:true });
</script>

<template>
  <section class="rounded-xl border border-fuchsia-900/60 bg-slate-950/40 p-3">
    <div class="flex items-start justify-between gap-3">
      <div><h4 class="text-xs font-bold text-fuchsia-200">工作流配置档案</h4><p class="mt-1 text-[10px] text-slate-500">原始 JSON 保持不变；覆盖和固定补充词单独保存。</p></div>
      <span v-if="loading" class="text-[10px] text-slate-500">读取中…</span>
    </div>
    <template v-if="detail && !loading">
      <div class="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
        <div v-for="item in reportItems" :key="item.key" class="rounded border px-2 py-1.5 text-[10px]" :class="item.mapped?'border-emerald-900/70 bg-emerald-950/20 text-emerald-300':item.severity==='risk'?'border-rose-800 bg-rose-950/30 text-rose-300':'border-amber-900/60 bg-amber-950/20 text-amber-300'">
          <div class="font-bold">{{ labels[item.key] || item.key }}</div><div class="mt-0.5 opacity-70">{{ item.mapped ? '已识别' : item.severity==='risk' ? '未识别 · 不能注入提示词' : '未识别 · 沿用原值' }}</div>
        </div>
      </div>
      <div v-if="!detail.mapping_report.can_inject_prompt" class="mt-3 rounded-lg border border-rose-800 bg-rose-950/30 p-2 text-[11px] text-rose-200">正向提示词节点未映射。可以按工作流原样测试，但“AI 整理并生成”和玩家提示词不会假装已注入。</div>
      <details class="mt-3 rounded-lg border border-slate-700 bg-slate-900/50 p-3">
        <summary class="cursor-pointer text-xs font-bold text-slate-300">人工指定节点映射</summary>
        <p class="mt-2 text-[10px] text-slate-500">自动识别不准确时再调整。候选来自工作流中输入名相符的节点，不会修改原始 JSON。</p>
        <div class="mt-3 space-y-2">
          <label v-for="item in reportItems.filter(row => row.candidates?.length)" :key="`map-${item.key}`" class="grid grid-cols-[7rem_1fr] items-center gap-2 text-[11px]">
            <span class="text-slate-400">{{ labels[item.key] || item.key }}</span>
            <select :value="JSON.stringify(form.mapping_overrides[item.key] || item.target || [])" class="field-input" @change="setMapping(item.key, $event.target.value)">
              <option value="">使用自动识别结果</option>
              <option v-for="candidate in item.candidates" :key="JSON.stringify(candidate.target)" :value="JSON.stringify(candidate.target)">{{ candidate.title }} · {{ candidate.node_id }}.{{ candidate.input_name }}</option>
            </select>
          </label>
        </div>
      </details>

      <label class="mt-4 block"><span class="field-label">玩家固定正向补充</span><textarea v-model="form.player_positive" rows="2" class="field-input resize-y" placeholder="长期附加在 AI 场景提示词之后；留空即可" /></label>
      <label class="mt-3 block"><span class="field-label">玩家固定负面补充</span><textarea v-model="form.player_negative" rows="2" class="field-input resize-y" placeholder="长期附加在工作流和本次负面词之后" /></label>
      <details class="mt-3 rounded-lg border border-slate-700 bg-slate-950/70 p-3">
        <summary class="cursor-pointer text-xs font-bold text-slate-300">预览提示词合成顺序</summary>
        <div class="mt-2 space-y-2 text-[10px] leading-relaxed"><p><b class="text-emerald-300">正向：</b>{{ previewPositive || '尚无内容' }}</p><p><b class="text-rose-300">负向：</b>{{ previewNegative || '尚无内容' }}</p><p class="text-slate-500">尖括号内容会在每次生成时替换为 AI 根据当前场景整理的结果；排列顺序不等于模型的确定权重。</p></div>
      </details>

      <label class="mt-4 flex items-center justify-between rounded-lg border border-slate-700 bg-slate-900/70 p-3">
        <span><b class="block text-xs text-slate-200">允许覆盖工作流设定</b><small class="text-[10px] text-slate-500">默认关闭；关闭时模型、尺寸和采样参数沿用工作流。</small></span>
        <input v-model="form.allow_overrides" type="checkbox" class="h-4 w-4 accent-fuchsia-500" />
      </label>
      <div v-if="form.allow_overrides" class="mt-3 grid grid-cols-2 gap-3">
        <label v-for="item in mappedOverrides" :key="item.key" class="block"><span class="field-label">{{ labels[item.key] }}</span><input v-model="form.overrides[item.key]" :type="item.key==='checkpoint'?'text':'number'" :placeholder="String(item.default ?? '沿用原值')" class="field-input" /></label>
      </div>
      <div class="mt-4 flex justify-end gap-2"><button class="action secondary" @click="reset">恢复工作流原值</button><button class="action primary" :disabled="saving" @click="save">{{ saving?'保存中…':'保存配置档案' }}</button></div>
    </template>
  </section>
</template>

<style scoped>
.field-label { display:block; margin-bottom:.35rem; color:rgb(148 163 184); font-size:.7rem; }
.field-input { width:100%; border:1px solid rgb(51 65 85); border-radius:.5rem; background:rgb(15 23 42); padding:.55rem .65rem; color:rgb(226 232 240); font-size:.75rem; outline:none; }
.field-input:focus { border-color:rgb(217 70 239); }
.action { border-radius:.5rem; padding:.5rem .75rem; font-size:.7rem; font-weight:700; }
.action:disabled { opacity:.5; }
.primary { background:rgb(192 38 211); color:white; }
.secondary { background:rgb(51 65 85); color:rgb(226 232 240); }
</style>
