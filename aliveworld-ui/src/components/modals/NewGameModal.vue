<!-- src/components/modals/NewGameModal.vue -->
<script setup>
import { onMounted, ref } from 'vue';
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';
import { gameStore } from '../../store/gameStore';
import { gameApi } from '../../api/gameApi';
import { configStore } from '../../store/configStore';
import { onboardingStore } from '../../store/onboardingStore';
import ExpandableTextarea from '../common/ExpandableTextarea.vue';
import StoryStartAssets from '../assets/StoryStartAssets.vue';
import { worldPackageApi } from '../../api/worldPackageApi';

const prefill = uiStore.newGamePrefill || {};
if (prefill.name) assetStore.newSaveName = prefill.name;
const newSaveDesc = ref(prefill.worldPremise || "");
const opening = ref('');
const creating = ref(false);
const selections = ref({ worldbook: '', player_character: '', style: '' });
const packages = ref([]);
const packageError = ref('');
const selectedPackage = ref(null);
const packageChooser = ref(false);
onMounted(() => assetStore.fetchAssets());
async function showPackages() {
  packageChooser.value = !packageChooser.value;
  if (!packageChooser.value) return;
  packageError.value = '';
  try { packages.value = (await worldPackageApi.list()).packages || []; }
  catch (error) { packageError.value = error.message; }
}
const resetPrefill = () => {
  uiStore.newGamePrefill = { name: '', worldPremise: '', fromOnboarding: false };
};
const close = () => {
  if (creating.value) return;
  uiStore.modals.newGame = false;
  resetPrefill();
};

const startNewGame = async () => {
  if (!assetStore.newSaveName.trim()) return uiStore.showToast("存档名不能为空！", "error"); 
  if (creating.value) return;
  creating.value = true;
  try {
    const data = selectedPackage.value
      ? await worldPackageApi.start(selectedPackage.value.package_id, selectedPackage.value.version, assetStore.newSaveName)
      : await gameApi.startGame({ save_name: assetStore.newSaveName, world_premise: newSaveDesc.value, opening: opening.value, story_settings: configStore.settings, ...selections.value });
    gameStore.registerSession(data, assetStore.newSaveName);
    configStore.applyStoryConfig(data);
    
    uiStore.modals.newGame = false;
    resetPrefill();
    await assetStore.fetchAssets();
    await assetStore.fetchLocalAssets(data.session_id);
    onboardingStore.complete();
    assetStore.newSaveName = "";
    newSaveDesc.value = "";
    uiStore.showToast("故事已创建");
  } catch (err) {
    uiStore.showToast(err.message || "创建故事失败", "error");
  } finally { creating.value = false; }
};
</script>
<template>
  <div class="fixed inset-0 bg-black/80 z-50 flex items-center justify-center backdrop-blur-sm p-4">
    <div data-testid="new-game-modal" role="dialog" aria-label="新建故事" class="bg-aw_panel border border-emerald-900/50 rounded-2xl w-full max-w-lg max-h-[90vh] shadow-2xl overflow-hidden flex flex-col slide-up">
      <div class="shrink-0 p-5 border-b border-slate-700 flex justify-between bg-slate-900/80">
        <h2 class="font-bold text-emerald-400 text-xl">新建故事</h2>
        <button @click="close" :disabled="creating" aria-label="关闭新建故事" class="text-slate-400 hover:text-white text-2xl disabled:opacity-40">✕</button>
      </div>
      <div class="p-6 space-y-5 overflow-y-auto">
        <div><label class="text-xs font-bold text-slate-400 block mb-1">故事名称</label><input data-testid="new-game-name" v-model="assetStore.newSaveName" :disabled="creating" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none focus:border-emerald-500" /></div>
        <button type="button" :disabled="creating" class="text-sm text-cyan-300 hover:underline" @click="showPackages">选择已安装的世界包</button>
        <section v-if="packageChooser" aria-label="选择世界包" class="space-y-2">
          <p v-if="packageError" role="alert" class="text-sm text-rose-300">{{ packageError }}</p>
          <p v-else-if="!packages.length" class="text-xs text-slate-400">暂无已安装世界包，可在资源库导入。</p>
          <button v-for="item in packages" :key="`${item.package_id}:${item.version}`" type="button" :disabled="creating" class="block w-full rounded-lg border border-slate-600 p-3 text-left text-slate-200" @click="selectedPackage=item; packageChooser=false">
            {{ item.name }} <span class="text-xs text-slate-400">v{{ item.version }}</span>
          </button>
        </section>
        <section v-if="selectedPackage" class="rounded-lg border border-cyan-800 bg-cyan-950/20 p-3 text-sm text-slate-200">
          <p>使用世界包：{{ selectedPackage.name }} · v{{ selectedPackage.version }}</p>
          <p class="mt-2 text-xs text-slate-400">采用作者的开场、资产与默认设置，不混入下方自选草稿。</p>
          <button type="button" :disabled="creating" class="mt-2 text-cyan-300" @click="selectedPackage=null">改为自行设置</button>
        </section>
        <template v-else>
        <StoryStartAssets v-model="selections" :disabled="creating" />
        <div>
          <label class="text-xs font-bold text-slate-400 block mb-1">故事与世界概述（选填）</label>
          <ExpandableTextarea data-testid="new-game-premise" v-model="newSaveDesc" :disabled="creating" label="新故事世界梗概" textarea-class="bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none focus:border-emerald-500 h-24 resize-none shadow-inner" />
        </div>
        <div>
          <label class="text-xs font-bold text-slate-400 block mb-1">开场（选填）</label>
          <ExpandableTextarea data-testid="new-game-opening" v-model="opening" :disabled="creating" label="故事开场" :maxlength="20000" placeholder="例如：傍晚，你站在山间驿站门口，屋内传来争执声。" textarea-class="bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none focus:border-emerald-500 h-24 resize-none" />
          <p class="text-xs text-slate-400 mt-2">写下当前地点和处境；留空也能开始。创建不会调用 AI，之后可载入资产并输入第一步行动。</p>
        </div>
        </template>
      </div>
      <div class="shrink-0 border-t border-slate-700 bg-slate-900 p-4">
        <button data-testid="new-game-submit" @click="startNewGame" :disabled="creating" class="w-full py-3 bg-emerald-600 hover:bg-emerald-500 rounded-xl font-bold shadow-lg disabled:opacity-50 transition text-lg">{{ creating ? '正在创建…' : '创建故事' }}</button>
      </div>
    </div>
  </div>
</template>
