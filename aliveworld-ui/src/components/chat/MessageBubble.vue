<!-- src/components/chat/MessageBubble.vue -->
<script setup>
import { computed, ref } from 'vue';
import { gameStore } from '../../store/gameStore';
import { effectiveStorySettings } from '../../store/configStore';
import { uiStore } from '../../store/uiStore';
import { gameApi } from '../../api/gameApi';
import { assetStore } from '../../store/assetStore';
import { formatUndercurrentDebug } from '../../utils/entityVisibility';
import { imageStore } from '../../store/imageStore';
import { imageApi } from '../../api/imageApi';
import { configStore } from '../../store/configStore';

const props = defineProps({
  msg: {
    type: Object,
    required: true
  }
});

const entityDebugText = computed(() => {
  if (props.msg.role !== 'undercurrent') return '';
  return formatUndercurrentDebug(props.msg.content, effectiveStorySettings.value, assetStore.entities.local);
});

const imageTasks = computed(() => imageStore.forMessage(props.msg.id));
const showImageForm = ref(false);
const imagePrompt = ref('');
const imageIntent = ref('scene_cg');
const submittingImage = ref(false);
const statusText = {
  queued: '等待提示词', compiling_prompt: '整理提示词', ready: '准备提交', submitted: '已提交',
  running: '生成中', succeeded: '已完成', failed: '生成失败', cancelled: '已取消'
};

const generateImage = async () => {
  const settings = configStore.globalSettings;
  if (!imagePrompt.value.trim()) return uiStore.showToast('请填写生图提示词', 'error');
  if (!settings.imageCheckpoint) return uiStore.showToast('请先在“设置 → 生图配置”选择 checkpoint', 'error');
  submittingImage.value = true;
  try {
    await imageStore.create(gameStore.sessionId, {
      intent: imageIntent.value,
      source_message_id: props.msg.id,
      provider_id: 'comfyui',
      workflow_id: settings.imageWorkflowId,
      prompt: {
        positive: imagePrompt.value.trim(),
        negative: settings.imageNegativePrompt,
        style_preference: settings.imageStylePreference,
        presentation_level: settings.imagePresentationLevel,
        width: imageIntent.value === 'scene_cg' ? 768 : 512,
        height: 768
      },
      context_snapshot: { story_text: props.msg.content },
      provider_options: { base_url: settings.imageApiUrl, checkpoint: settings.imageCheckpoint }
    });
    showImageForm.value = false;
    imagePrompt.value = '';
    uiStore.showToast('生图任务已进入后台队列');
  } catch (error) { uiStore.showToast(error.message, 'error'); }
  finally { submittingImage.value = false; }
};

const doReroll = async () => {
  if (!gameStore.sessionId || gameStore.isProcessing) return;
  gameStore.isProcessing = true;
  try {
    const res = await gameApi.rerollTurn(gameStore.sessionId, {
      entities_enabled: effectiveStorySettings.value.entitiesEnabled
    });
    gameStore.chatLog = res.chat_messages;
    gameStore.syncState(res.state);
    
    // 自动滚动到底部
    setTimeout(() => {
      const c = document.getElementById('chat-container');
      if (c) c.scrollTop = c.scrollHeight;
    }, 100);
  } catch (e) {
    uiStore.showToast("命运已成定局，此处无法重掷", "error");
  } finally {
    gameStore.isProcessing = false;
    assetStore.fetchLocalAssets(gameStore.sessionId); // 刷新实体库
  }
};
</script>

<template>
  <div class="flex flex-col" :class="msg.role === 'user' ? 'items-end' : 'items-start'">
    
    <!-- 🎲 动态未来候选折叠面板 -->
    <div v-if="msg.role === 'reactions' && effectiveStorySettings.showFutures" class="w-full max-w-[85%] bg-amber-950/60 border border-amber-700/50 rounded-xl overflow-hidden backdrop-blur-md shadow-lg mb-2">
      <details class="group">
        <summary class="cursor-pointer px-4 py-2.5 text-xs text-amber-400 font-bold flex justify-between items-center hover:bg-amber-900/50 transition select-none">
          <span>🎲 观测到 {{ msg.content.length }} 种时间线</span>
          <span class="group-open:rotate-180 transition">▼</span>
        </summary>
        <div class="px-4 py-3 border-t border-amber-900/50 space-y-2">
          <div v-for="r in msg.content" :key="r.id" class="flex items-start gap-3 text-xs bg-black/40 p-2 rounded hover:bg-black/60 transition" :class="r.eligible === false ? 'text-slate-500' : 'text-amber-200'">
            <div class="min-w-16 text-center font-mono font-bold rounded px-1" :class="r.eligible === false ? 'bg-slate-700/40' : 'bg-amber-600/40'">
              {{ r.eligible === false ? '不成立' : `权重 ${r.weight}` }}
            </div>
            <div class="flex-1">
              <div>{{ r.description }}</div>
              <div v-if="r.basis?.length" class="mt-1 text-[10px] opacity-65">依据：{{ r.basis.join('；') }}</div>
            </div>
          </div>
        </div>
      </details>
    </div>

    <!-- 🎯 命运掷骰裁定结果 -->
    <div v-else-if="msg.role === 'system' && effectiveStorySettings.showDice" class="text-xs text-rose-400 mb-2 px-4 py-2 bg-rose-950/80 border border-rose-700/50 rounded-lg backdrop-blur-md italic shadow-md max-w-[85%] flex justify-between items-center group">
      <span>{{ msg.content }}</span>
      <button v-if="effectiveStorySettings.allowReroll" @click="doReroll" class="hidden group-hover:block px-3 py-1 bg-rose-800 hover:bg-rose-600 text-white rounded text-[10px] font-bold transition ml-4 shadow shrink-0">
        🔄 重掷
      </button>
    </div>

    <!-- 🌌 暗流实体推演结果 -->
    <div v-else-if="entityDebugText" class="text-xs text-purple-400 mb-2 px-4 py-2 bg-purple-950/60 border border-purple-800/50 rounded-lg backdrop-blur-md italic shadow-md max-w-[85%] shadow-purple-900/20">
      <span class="flex items-center gap-2"><span>👾</span> {{ entityDebugText }}</span>
    </div>

    <div v-else-if="msg.role === 'influence' && effectiveStorySettings.showInfluenceBubbles" class="text-xs text-fuchsia-300 mb-2 px-4 py-2 bg-fuchsia-950/50 border border-fuchsia-800/50 rounded-lg max-w-[85%]">
      <div class="font-bold">🕸️ 暗流影响已触发</div>
      <div class="mt-1">{{ msg.content.summary }}</div>
      <div class="mt-1 text-fuchsia-400/80">结果：{{ msg.content.result }}</div>
      <div class="mt-1 font-mono text-[9px] text-slate-500">{{ msg.content.id }}</div>
    </div>

    <!-- 💬 玩家与 AI 对话正文 -->
    <div v-else-if="msg.role === 'user' || msg.role === 'ai'" class="w-full max-w-[85%]">
      <div class="rounded-2xl p-5 whitespace-pre-wrap leading-relaxed shadow-2xl text-[15px] backdrop-blur-md"
           :class="msg.role === 'user' ? 'bg-indigo-600/95 text-white rounded-br-sm' : 'bg-slate-900/90 border border-slate-600 text-slate-200 rounded-bl-sm'">
        {{ gameStore.formatContent(msg.content) }}
      </div>
      <div v-if="msg.role === 'ai'" class="mt-2">
        <button v-if="!showImageForm" @click="showImageForm = true" class="text-[11px] text-fuchsia-300 hover:text-fuchsia-200 px-2 py-1 rounded border border-fuchsia-800/60 bg-fuchsia-950/20">🎨 生成此处 CG</button>
        <div v-else class="rounded-xl border border-fuchsia-800/60 bg-slate-950/90 p-3 space-y-2">
          <div class="flex gap-2">
            <select v-model="imageIntent" class="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-slate-200">
              <option value="scene_cg">场景 CG</option><option value="character_cg">角色 CG</option>
            </select>
            <span class="text-[10px] text-slate-500 self-center">直接提示词模式，不调用 LLM</span>
          </div>
          <textarea v-model="imagePrompt" rows="3" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-xs text-slate-200 resize-y" placeholder="描述希望生成的画面……" />
          <div class="flex justify-end gap-2">
            <button @click="showImageForm = false" class="px-3 py-1 text-xs bg-slate-700 rounded">取消</button>
            <button @click="generateImage" :disabled="submittingImage" class="px-3 py-1 text-xs bg-fuchsia-700 hover:bg-fuchsia-600 disabled:opacity-50 rounded text-white">{{ submittingImage ? '提交中…' : '开始生成' }}</button>
          </div>
        </div>
        <div v-for="task in imageTasks" :key="task.id" class="mt-2 rounded-xl border border-fuchsia-900/60 bg-slate-950/80 p-3">
          <div class="flex justify-between items-center text-xs"><span class="text-fuchsia-300">🖼️ {{ statusText[task.status] || task.status }}</span><span class="font-mono text-[9px] text-slate-600">{{ task.id }}</span></div>
          <div v-if="['queued','compiling_prompt','ready','submitted','running'].includes(task.status)" class="mt-2">
            <div class="h-1.5 rounded bg-slate-800 overflow-hidden"><div class="h-full bg-fuchsia-500 transition-all" :class="task.progress ? '' : 'animate-pulse w-1/3'" :style="task.progress ? { width: `${task.progress * 100}%` } : {}"></div></div>
            <button @click="imageStore.cancel(task.id)" class="mt-2 text-[10px] text-slate-400 hover:text-rose-300">取消任务</button>
          </div>
          <div v-else-if="task.status === 'failed'" class="mt-2 text-xs text-rose-300">{{ task.error_message || '未知错误' }} <button @click="imageStore.retry(task.id)" class="ml-2 underline">重试</button></div>
          <div v-else-if="task.status === 'cancelled'" class="mt-2 text-xs text-slate-500">任务已取消 <button @click="imageStore.retry(task.id)" class="ml-2 underline">重新生成</button></div>
          <div v-else-if="task.status === 'succeeded'" class="mt-2 grid gap-2">
            <img v-for="url in task.output_images" :key="url" :src="imageApi.absoluteImageUrl(url)" class="max-h-[32rem] rounded-lg border border-slate-700 object-contain bg-black" />
          </div>
        </div>
      </div>
    </div>

  </div>
</template>
