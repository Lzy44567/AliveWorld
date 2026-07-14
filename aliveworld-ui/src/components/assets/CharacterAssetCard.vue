<script setup>
defineProps({
  item: { type: Object, required: true },
  scope: { type: String, required: true },
  portraitUrl: { type: String, default: '' },
  deleteConfirm: { type: Boolean, default: false },
});
defineEmits(['toggle', 'edit', 'portrait', 'pull', 'push', 'request-delete', 'confirm-delete', 'cancel-delete', 'zoom']);
</script>

<template>
  <article class="overflow-hidden rounded-xl border border-slate-700 bg-aw_panel shadow transition hover:border-indigo-500" :class="item.is_active === false ? 'opacity-60 grayscale' : ''">
    <div class="grid min-h-56" :class="portraitUrl ? 'grid-cols-[9.5rem_minmax(0,1fr)]' : 'grid-cols-1'">
      <button v-if="portraitUrl" @click="$emit('zoom', portraitUrl)" class="group/portrait relative min-h-56 overflow-hidden border-r border-fuchsia-900/50 bg-black" title="点击放大立绘">
        <img :src="portraitUrl" class="absolute inset-0 h-full w-full object-contain transition group-hover/portrait:scale-[1.02]" />
      </button>
      <div class="flex min-w-0 flex-col p-3">
        <div class="flex items-start justify-between gap-2">
          <h4 class="min-w-0 truncate text-sm font-bold text-slate-200"><span v-if="item.is_player" class="mr-1 text-amber-400" title="玩家化身">👑</span>{{ item.name }}</h4>
          <button v-if="scope==='local'" @click="$emit('toggle')" role="switch" :aria-checked="item.is_active !== false" class="inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-1 text-[9px] font-bold" :class="item.is_active === false ? 'border-slate-600 bg-slate-800 text-slate-400' : 'border-emerald-700/70 bg-emerald-950/60 text-emerald-300'">
            <span class="flex h-4 w-8 items-center rounded-full p-0.5" :class="item.is_active === false ? 'justify-start bg-slate-600' : 'justify-end bg-emerald-500'"><span class="h-3 w-3 rounded-full bg-white" /></span>{{ item.is_active === false ? '封存' : '启用' }}
          </button>
        </div>
        <div class="mt-2 flex flex-wrap gap-1"><span v-for="tag in item.tags" :key="tag" class="rounded border border-slate-700 bg-slate-800 px-1.5 py-0.5 text-[9px] text-slate-400">{{ tag }}</span></div>
        <p class="mt-2 line-clamp-4 text-[11px] leading-relaxed text-slate-500">{{ item.desc }}</p>
        <div class="mt-auto grid grid-cols-2 gap-2 pt-4 text-[10px] font-bold">
          <button @click="$emit('edit')" class="rounded bg-slate-800 py-1.5 text-slate-300 hover:bg-slate-700">✏️ {{ scope === 'local' ? '微调' : '编辑' }}</button>
          <button v-if="scope==='local'" @click="$emit('portrait')" class="rounded border border-fuchsia-800/60 bg-fuchsia-900/40 py-1.5 text-fuchsia-300 hover:bg-fuchsia-700 hover:text-white">🎨 立绘</button>
          <button v-if="scope==='global'" @click="$emit('pull')" class="rounded border border-indigo-700/50 bg-indigo-900/50 py-1.5 text-indigo-300 hover:bg-indigo-600 hover:text-white">⬇️ 载入局内</button>
          <button v-if="scope==='local'" @click="$emit('push')" class="rounded border border-emerald-700/50 bg-emerald-900/50 py-1.5 text-emerald-300 hover:bg-emerald-600 hover:text-white">⬆️ 推送全局</button>
          <template v-if="deleteConfirm">
            <button @click="$emit('confirm-delete')" class="rounded border border-rose-500 bg-rose-700 py-1.5 text-white">确认删除</button>
            <button @click="$emit('cancel-delete')" class="rounded border border-slate-600 bg-slate-700 py-1.5 text-slate-300">取消</button>
          </template>
          <button v-else @click="$emit('request-delete')" class="rounded border border-rose-900/50 bg-rose-900/30 py-1.5 text-rose-400 hover:bg-rose-600 hover:text-white">🗑 删除</button>
        </div>
        <p v-if="scope==='global'" class="mt-2 text-[9px] leading-relaxed text-slate-600">全局立绘将在角色工坊使用独立的全局任务域，不借用故事存档。</p>
      </div>
    </div>
  </article>
</template>
