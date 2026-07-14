<script setup>
const options = defineModel({ type: Object, required: true });
const presets = [
  { label: '省显存 · 512×768', width: 512, height: 768 },
  { label: '标准 · 768×768', width: 768, height: 768 },
  { label: '竖图 · 768×1024', width: 768, height: 1024 },
  { label: '横图 · 1024×768', width: 1024, height: 768 },
];
const applyPreset = (event) => {
  const preset = presets[Number(event.target.value)];
  if (preset) Object.assign(options.value, preset);
};
</script>

<template>
  <div class="space-y-2 rounded-lg border border-slate-800 bg-slate-900/50 p-3">
    <div class="grid grid-cols-2 gap-2">
      <label class="text-[10px] text-slate-400">图片尺寸
        <select @change="applyPreset" class="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1.5 text-xs text-slate-200">
          <option value="">自定义 {{ options.width }}×{{ options.height }}</option>
          <option v-for="(preset,index) in presets" :key="preset.label" :value="index">{{ preset.label }}</option>
        </select>
      </label>
      <label class="text-[10px] text-slate-400">生成数量
        <select v-model.number="options.count" class="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1.5 text-xs text-slate-200"><option v-for="n in 4" :key="n" :value="n">{{ n }} 张</option></select>
      </label>
    </div>
    <details class="text-[10px] text-slate-400"><summary class="cursor-pointer select-none hover:text-slate-200">高级参数</summary>
      <div class="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-5">
        <label>宽<input v-model.number="options.width" type="number" min="64" max="4096" step="8" class="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1.5 text-xs"></label>
        <label>高<input v-model.number="options.height" type="number" min="64" max="4096" step="8" class="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1.5 text-xs"></label>
        <label>迭代步数<input v-model.number="options.steps" type="number" min="1" max="100" class="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1.5 text-xs"></label>
        <label>CFG<input v-model.number="options.cfg" type="number" min="1" max="30" step="0.5" class="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1.5 text-xs"></label>
        <label>数量<input v-model.number="options.count" type="number" min="1" max="4" class="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-1.5 text-xs"></label>
      </div>
      <p class="mt-2 text-amber-500/80">更高分辨率、数量和步数会明显增加显存占用与等待时间；RTX 3050 建议先用“省显存”与单张。</p>
    </details>
  </div>
</template>
