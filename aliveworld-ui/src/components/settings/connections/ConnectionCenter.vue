<script setup>
import { computed, onMounted, ref } from 'vue';
import ConnectionEditor from './ConnectionEditor.vue';
import TaskRouting from './TaskRouting.vue';
import FieldHelp from '../../common/FieldHelp.vue';
import { connectionStore } from '../../../store/connectionStore';
import { configStore } from '../../../store/configStore';
import { uiStore } from '../../../store/uiStore';

const tab = ref('text');
const editor = ref(null);
const openMenuId = ref('');
const deleteTarget = ref(null);
const cloneTarget = ref(null);
const cloneName = ref('');

const visibleProfiles = computed(() => connectionStore.profiles.filter(item => item.category === tab.value));
const storyProfileId = computed(() => connectionStore.routes.story?.connection_id || '');
const imageProfileId = computed(() => connectionStore.routes.image_generation?.connection_id || '');

onMounted(async () => {
  try {
    await connectionStore.refresh();
  } catch (error) {
    uiStore.showToast(error.message, 'error');
  }
});

function isPrimary(profile) {
  return profile.category === 'text' ? profile.id === storyProfileId.value : profile.id === imageProfileId.value;
}

async function makePrimary(profile) {
  const task = profile.category === 'text' ? 'story' : 'image_generation';
  try {
    await connectionStore.setRoute(task, { connectionId: profile.id, inheritFrom: '', modelOverride: '' });
    await configStore.fetchFromBackend();
    uiStore.apiSetupRequired = !configStore.globalSettings.apiReady;
    uiStore.showToast(`已设为${profile.category === 'text' ? '主文本' : '图片生成'}接口`);
  } catch (error) {
    uiStore.showToast(error.message, 'error');
  }
}

async function testProfile(profile) {
  openMenuId.value = '';
  try {
    await connectionStore.test(profile.id);
    uiStore.showToast(`${profile.name} 连接正常`);
  } catch (error) {
    uiStore.showToast(error.message, 'error');
  }
}

async function confirmClone() {
  try {
    await connectionStore.clone(cloneTarget.value.id, cloneName.value);
    uiStore.showToast('接口配置已克隆');
    cloneTarget.value = null;
  } catch (error) {
    uiStore.showToast(error.message, 'error');
  }
}

async function confirmDelete() {
  try {
    await connectionStore.remove(deleteTarget.value.id);
    uiStore.showToast('接口配置已删除');
    deleteTarget.value = null;
  } catch (error) {
    uiStore.showToast(error.message, 'error');
  }
}
</script>

<template>
  <section>
    <div class="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h3 class="flex items-center text-sm font-bold text-emerald-400">接口与模型<FieldHelp text="接口配置负责地址和密钥；功能用途决定正文、记忆、工坊等分别使用哪条接口。普通玩家只需要设置主文本接口。" /></h3>
        <p class="mt-1 text-[10px] leading-relaxed text-slate-500">普通模式只选择主接口；不同功能使用不同模型时再展开高级分配。</p>
      </div>
      <button class="rounded-lg bg-emerald-700 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-600" @click="editor={ category:tab, profile:null }">＋ 新增接口</button>
    </div>

    <div v-if="uiStore.apiSetupRequired" class="mb-4 rounded-xl border border-amber-500/70 bg-amber-950/30 p-4 text-xs leading-relaxed text-amber-100">
      <div class="font-bold">👋 首次使用：请新增或编辑一条语言接口</div>
      <p class="mt-1 text-amber-200/80">填写地址、API Key 和默认模型，保存并测试后设为主文本接口。密钥只保存在本机 UserData。</p>
    </div>

    <div class="mb-4 grid grid-cols-2 rounded-xl border border-slate-700 bg-slate-950 p-1 text-xs">
      <button class="rounded-lg py-2 font-bold" :class="tab==='text'?'bg-cyan-800 text-white':'text-slate-500'" @click="tab='text'">语言</button>
      <button class="rounded-lg py-2 font-bold" :class="tab==='image'?'bg-fuchsia-800 text-white':'text-slate-500'" @click="tab='image'">生图</button>
    </div>

    <div v-if="connectionStore.loading && !connectionStore.loaded" class="rounded-xl border border-dashed border-slate-700 p-8 text-center text-xs text-slate-500">正在读取本机接口配置……</div>
    <div v-else-if="!visibleProfiles.length" class="rounded-xl border border-dashed border-slate-700 p-8 text-center">
      <p class="text-sm text-slate-400">还没有{{ tab==='text'?'语言':'生图' }}接口</p>
      <button class="mt-3 rounded-lg bg-slate-700 px-3 py-2 text-xs text-white" @click="editor={ category:tab, profile:null }">创建第一条接口</button>
    </div>

    <div v-else class="space-y-3">
      <article
        v-for="profile in visibleProfiles"
        :key="profile.id"
        class="relative rounded-xl border bg-slate-900/80 p-4 transition"
        :class="isPrimary(profile)?'border-cyan-500 shadow-[0_0_0_1px_rgba(6,182,212,.12)]':'border-slate-700'"
      >
        <div class="flex items-start gap-3">
          <div class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-800 text-lg">{{ profile.category==='text'?'◉':'◈' }}</div>
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <h4 class="truncate text-sm font-bold text-slate-100">{{ profile.name }}</h4>
              <span v-if="isPrimary(profile)" class="rounded bg-cyan-800 px-2 py-0.5 text-[9px] font-bold text-cyan-100">{{ profile.category==='text'?'主文本接口':'当前生图接口' }}</span>
              <span v-if="!profile.enabled" class="rounded bg-slate-700 px-2 py-0.5 text-[9px] text-slate-400">已停用</span>
            </div>
            <p class="mt-1 truncate text-[10px] text-slate-500">{{ profile.base_url || '尚未填写接口地址' }}</p>
            <p v-if="profile.category==='text'" class="mt-1 text-[10px] text-slate-400">{{ profile.default_model || '尚未填写默认模型' }} · {{ profile.api_key_configured?'密钥已配置':'未配置密钥' }}</p>
            <p v-else class="mt-1 text-[10px] text-slate-400">ComfyUI · {{ profile.last_test?.ok?'最近测试成功':'尚未测试或不可用' }}</p>
          </div>
          <button class="rounded-lg px-3 py-1 text-lg text-slate-400 hover:bg-slate-800 hover:text-white" @click="openMenuId=openMenuId===profile.id?'':profile.id">⋮</button>
        </div>
        <div class="mt-3 flex justify-end">
          <button v-if="!isPrimary(profile)" class="rounded-lg border border-cyan-800 px-3 py-1.5 text-[10px] text-cyan-300 hover:bg-cyan-950" @click="makePrimary(profile)">设为{{ profile.category==='text'?'主文本':'图片生成' }}接口</button>
        </div>
        <div v-if="openMenuId===profile.id" class="absolute right-3 top-12 z-10 w-32 overflow-hidden rounded-xl border border-slate-600 bg-slate-950 py-1 text-xs shadow-2xl">
          <button class="menu-item" @click="editor={ category:profile.category, profile };openMenuId=''">编辑</button>
          <button class="menu-item" @click="testProfile(profile)">测试连接</button>
          <button class="menu-item" @click="cloneTarget=profile;cloneName=`${profile.name} 副本`;openMenuId=''">克隆</button>
          <button class="menu-item text-rose-400" @click="deleteTarget=profile;openMenuId=''">删除</button>
        </div>
      </article>
    </div>

    <TaskRouting v-if="connectionStore.loaded && tab==='text'" />

    <ConnectionEditor v-if="editor" :category="editor.category" :profile="editor.profile" @close="editor=null" @saved="connectionStore.refresh()" />

    <Teleport to="body">
      <div v-if="cloneTarget" class="fixed inset-0 z-[85] flex items-center justify-center bg-black/75 p-4" @mousedown.self="cloneTarget=null">
        <section class="w-full max-w-sm rounded-2xl border border-cyan-700 bg-slate-900 p-5 shadow-2xl">
          <h3 class="font-bold text-slate-100">克隆接口配置</h3>
          <p class="mt-1 text-[10px] text-slate-500">会复制地址、密钥和默认模型，但不会自动分配给任何功能。</p>
          <input v-model="cloneName" class="mt-4 w-full rounded-lg border border-slate-700 bg-slate-950 p-3 text-sm text-slate-200 outline-none focus:border-cyan-500">
          <div class="mt-4 flex justify-end gap-2"><button class="rounded-lg bg-slate-700 px-3 py-2 text-xs" @click="cloneTarget=null">取消</button><button class="rounded-lg bg-cyan-700 px-3 py-2 text-xs font-bold text-white" @click="confirmClone">确认克隆</button></div>
        </section>
      </div>
      <div v-if="deleteTarget" class="fixed inset-0 z-[85] flex items-center justify-center bg-black/75 p-4" @mousedown.self="deleteTarget=null">
        <section class="w-full max-w-sm rounded-2xl border border-rose-800 bg-slate-900 p-5 shadow-2xl">
          <h3 class="font-bold text-slate-100">删除“{{ deleteTarget.name }}”？</h3>
          <p class="mt-2 text-xs leading-relaxed text-slate-400">正在被正文或其他功能使用的接口不会被删除，必须先重新分配。删除后密钥也会从本机配置移除。</p>
          <div class="mt-4 flex justify-end gap-2"><button class="rounded-lg bg-slate-700 px-3 py-2 text-xs" @click="deleteTarget=null">取消</button><button class="rounded-lg bg-rose-700 px-3 py-2 text-xs font-bold text-white" @click="confirmDelete">确认删除</button></div>
        </section>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.menu-item {
  @apply block w-full px-3 py-2 text-left text-slate-300 hover:bg-slate-800;
}
</style>
