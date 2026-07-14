<script setup>
defineProps({ characterName: { type: String, required: true }, portraitScope: { type: String, default: 'none' } });
defineEmits(['confirm', 'cancel']);
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[150] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm" @click.self="$emit('cancel')">
      <section class="w-full max-w-md rounded-2xl border border-rose-800/70 bg-aw_panel p-5 shadow-2xl">
        <div class="flex gap-3"><div class="text-2xl">⚠️</div><div><h3 class="font-bold text-rose-300">删除本局角色“{{ characterName }}”？</h3><p class="mt-2 text-xs leading-relaxed text-slate-400">角色卡将从当前存档永久删除。</p><p v-if="portraitScope==='local'" class="mt-2 text-xs leading-relaxed text-amber-300">该角色的本局立绘图片和生图任务记录也会一并删除。</p><p v-else-if="portraitScope==='global'" class="mt-2 text-xs leading-relaxed text-slate-400">本局会移除立绘关联，但全局角色卡与全局原图不会删除。</p></div></div>
        <div class="mt-5 grid grid-cols-2 gap-3"><button @click="$emit('cancel')" class="rounded-lg border border-slate-600 bg-slate-800 py-2 text-xs font-bold text-slate-300 hover:bg-slate-700">取消</button><button @click="$emit('confirm')" class="rounded-lg border border-rose-500 bg-rose-700 py-2 text-xs font-bold text-white hover:bg-rose-600">确认删除</button></div>
      </section>
    </div>
  </Teleport>
</template>
