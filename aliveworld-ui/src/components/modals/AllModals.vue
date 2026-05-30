<script setup>
import { uiStore } from '../../store/uiStore';
import { assetStore } from '../../store/assetStore';
import { configStore } from '../../store/configStore';
import { gameStore } from '../../store/gameStore'; // 新增
import { gameApi } from '../../api/gameApi';     // 新增

// [新增] 发起创世 API 请求
const startNewGame = async () => {
  if (!assetStore.newSaveName.trim()) { alert("⚠️ 命运必须有一个名字 (存档名为空)！"); return; }
  gameStore.isProcessing = true;
  try {
    const payload = { 
      style_name: assetStore.selectedStyle, 
      worldbook_name: assetStore.selectedWorldbook, 
      save_name: assetStore.newSaveName 
    };
    const data = await gameApi.startGame(payload);
    
    // 同步到 UI 引擎
    gameStore.sessionId = data.session_id;
    gameStore.chatLog = data.chat_messages;
    gameStore.syncState(data.state);
    
    // 关闭弹窗，刷新一遍右侧的存档列表
    uiStore.modals.newGame = false;
    await assetStore.fetchAssets();
  } catch (err) {
    alert("创世失败，请检查 Python 后端是否启动！");
  } finally {
    gameStore.isProcessing = false;
  }
};
</script>

<template>
  <!-- ⚙️ 设置弹窗 -->
  <div v-if="uiStore.modals.settings" class="fixed inset-0 bg-black/80 z-50 flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-aw_panel border border-slate-600 rounded-2xl w-full max-w-3xl shadow-2xl flex flex-col slide-up overflow-hidden h-[75vh]">
      <div class="p-5 border-b border-slate-700 flex justify-between bg-slate-900/80">
        <h2 class="font-bold text-slate-200 text-xl">⚙️ 系统设置与模型核心</h2>
        <button @click="uiStore.modals.settings=false" class="text-slate-400 hover:text-white text-xl">✕</button>
      </div>
      <div class="flex flex-1 overflow-hidden">
        <div class="w-48 bg-slate-900/50 border-r border-slate-700 p-3 space-y-1">
          <button class="w-full text-left px-3 py-2 text-sm font-bold bg-slate-800 text-emerald-400 rounded">🔌 API 配置</button>
          <button class="w-full text-left px-3 py-2 text-sm font-bold text-slate-400 hover:bg-slate-800 rounded">🎛️ 调试与沉浸</button>
        </div>
        <div class="flex-1 p-6 overflow-y-auto space-y-8 bg-slate-800/20 custom-scrollbar">
          <section>
            <h3 class="text-sm font-bold text-emerald-400 mb-3 border-b border-slate-700 pb-2">大语言模型配置</h3>
            <input type="password" v-model="configStore.globalSettings.apiKey" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none" placeholder="sk-..." />
          </section>
          <section>
            <h3 class="text-sm font-bold text-rose-400 mb-4 border-b border-slate-700 pb-2">开发者调试选项</h3>
            <div class="grid grid-cols-2 gap-4">
              <label class="flex items-center gap-3 text-sm text-slate-400 cursor-pointer"><input type="checkbox" v-model="configStore.settings.showFutures" class="rounded bg-slate-800 border-slate-600 text-rose-500"><span>显示未来可能性包 (N*n)</span></label>
              <label class="flex items-center gap-3 text-sm text-slate-400 cursor-pointer"><input type="checkbox" v-model="configStore.settings.allowReroll" class="rounded bg-slate-800 border-slate-600 text-rose-500"><span>开启“重掷未来”</span></label>
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>

  <!-- ✨ 创世弹窗 -->
  <div v-if="uiStore.modals.newGame" class="fixed inset-0 bg-black/80 z-50 flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-aw_panel border border-emerald-900/50 rounded-2xl w-full max-w-3xl shadow-2xl overflow-hidden flex flex-col slide-up">
      <div class="p-5 border-b border-slate-700 flex justify-between bg-slate-900/80">
        <h2 class="font-bold text-emerald-400 text-xl">✨ 创世协议</h2>
        <button @click="uiStore.modals.newGame=false" class="text-slate-400 hover:text-white text-2xl">✕</button>
      </div>
      <div class="p-6 space-y-4">
        <!-- 绑定 v-model 到 assetStore.newSaveName -->
        <div><label class="text-xs font-bold text-slate-400 block mb-1">📝 时间线命名</label><input v-model="assetStore.newSaveName" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none" placeholder="例如：废土远征纪" /></div>
        <div class="grid grid-cols-2 gap-4">
           <!-- 绑定后端循环的真实下拉数据 -->
           <div><label class="text-xs font-bold text-slate-400 block mb-1">🌍 世界书</label><select v-model="assetStore.selectedWorldbook" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none"><option>无界域 (暂不加载)</option><option v-for="w in assetStore.availableWorldbooks" :key="w" :value="w">{{ w }}</option></select></div>
           <div><label class="text-xs font-bold text-slate-400 block mb-1">🎭 文风卡</label><select v-model="assetStore.selectedStyle" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none"><option>默认 (无)</option><option v-for="s in assetStore.availableStyles" :key="s" :value="s">{{ s }}</option></select></div>
        </div>
        <!-- 绑定 @click -->
        <button @click="startNewGame" :disabled="gameStore.isProcessing" class="w-full py-4 mt-2 bg-emerald-600 hover:bg-emerald-500 rounded-xl font-bold shadow-lg disabled:opacity-50 transition">降临新世界</button>
      </div>
    </div>
  </div>

  <!-- ⬇️ 插入角色弹窗 -->
  <div v-if="uiStore.modals.insertChar" class="fixed inset-0 bg-black/80 z-[60] flex items-center justify-center backdrop-blur-sm p-4">
    <div class="bg-aw_panel border border-indigo-900/50 rounded-2xl w-[500px] shadow-2xl flex flex-col slide-up overflow-hidden">
      <div class="p-4 border-b border-slate-700 flex justify-between bg-slate-900/80"><h2 class="font-bold text-indigo-400 text-lg">⬇️ 引入局内: {{ assetStore.insertCharData.name }}</h2><button @click="uiStore.modals.insertChar=false" class="text-slate-400 hover:text-white text-xl">✕</button></div>
      <div class="p-6 space-y-4">
        <p class="text-xs text-slate-400">AI 会根据你的描述自动安排他/她的出场方式。</p>
        <textarea v-model="assetStore.insertCharData.entrance" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 outline-none h-28 resize-none shadow-inner" placeholder="例如：突然踹开酒馆的大门，向玩家求救..."></textarea>
        <div class="flex justify-end gap-3 mt-4">
          <button @click="uiStore.modals.insertChar=false" class="px-4 py-2 bg-slate-800 text-slate-300 rounded font-bold hover:bg-slate-700">取消</button>
          <button class="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded font-bold shadow-lg">发送指令</button>
        </div>
      </div>
    </div>
  </div>
</template>