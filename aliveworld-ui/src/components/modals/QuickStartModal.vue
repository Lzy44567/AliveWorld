<script setup>
import { onboardingStore } from '../../store/onboardingStore';
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[75] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
      <section class="w-full max-w-2xl overflow-hidden rounded-2xl border border-emerald-700/70 bg-slate-900 shadow-2xl">
        <header class="border-b border-slate-700 bg-slate-950/70 px-6 py-5">
          <p class="text-xs font-bold uppercase tracking-[0.24em] text-emerald-400">AliveWorld 快速开始</p>
          <h2 class="mt-2 text-2xl font-black text-slate-100">让第一个世界活起来</h2>
          <p class="mt-2 text-sm leading-6 text-slate-400">故事没有固定路线。你描述行动，世界书维持规则，角色与暗流实体在幕后继续行动；所有内容都会保存到本机。</p>
        </header>

        <div class="grid gap-3 p-6 sm:grid-cols-2">
          <button class="rounded-xl border border-emerald-700/60 bg-emerald-950/25 p-4 text-left transition hover:border-emerald-400 hover:bg-emerald-950/45" @click="onboardingStore.openNewGame({ starter: true })">
            <div class="text-base font-bold text-emerald-200">✨ 使用入门梗概</div>
            <p class="mt-2 text-xs leading-5 text-slate-400">载入一个可自由修改的边境奇幻起点，适合立即测试正文、行动建议和世界变化。</p>
          </button>
          <button class="rounded-xl border border-indigo-700/60 bg-indigo-950/25 p-4 text-left transition hover:border-indigo-400 hover:bg-indigo-950/45" @click="onboardingStore.openNewGame()">
            <div class="text-base font-bold text-indigo-200">📝 从空白故事开始</div>
            <p class="mt-2 text-xs leading-5 text-slate-400">只打开创世窗口，由你自己填写故事线名称和世界梗概。</p>
          </button>
        </div>

        <div class="mx-6 mb-5 rounded-xl border border-slate-700 bg-slate-950/55 p-4 text-xs leading-6 text-slate-400">
          <strong class="text-slate-200">创建后怎么玩：</strong>
          阅读开场，在底部描述你要做什么；也可以直接点击 AI 给出的快捷行动。需要排查资产或模型时，顶部“日志”会显示实际发送内容。
        </div>

        <footer class="flex flex-wrap items-center justify-between gap-3 border-t border-slate-700 bg-slate-950/40 px-6 py-4">
          <button class="text-xs text-slate-500 hover:text-slate-300" @click="onboardingStore.disable()">不再提示</button>
          <button class="rounded-lg bg-slate-700 px-4 py-2 text-xs font-bold text-slate-200 hover:bg-slate-600" @click="onboardingStore.snooze()">稍后再说</button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>
