<script setup>
import { computed, ref } from 'vue';
import { connectionStore } from '../../../store/connectionStore';

const props = defineProps({
  modelValue: { type: String, default: '' },
  profileId: { type: String, default: '' },
});
const emit = defineEmits(['update:modelValue']);

const models = ref([]);
const loading = ref(false);
const message = ref('');
const open = ref(false);
const filtered = computed(() => {
  const query = props.modelValue.trim().toLocaleLowerCase();
  return models.value.filter(item => !query || item.toLocaleLowerCase().includes(query)).slice(0, 30);
});

async function discover(refresh = false) {
  if (!props.profileId || loading.value) return;
  loading.value = true;
  try {
    const result = await connectionStore.discoverModels(props.profileId, refresh);
    models.value = result.models || [];
    message.value = result.message || '';
    open.value = Boolean(models.value.length);
  } catch (error) {
    message.value = `${error.message}；仍可手动填写。`;
  } finally {
    loading.value = false;
  }
}

function choose(model) {
  emit('update:modelValue', model);
  open.value = false;
}
</script>

<template>
  <div class="relative">
    <div class="flex gap-2">
      <input
        :value="modelValue"
        class="connection-field min-w-0 flex-1"
        placeholder="输入或检索模型名"
        autocomplete="off"
        @input="emit('update:modelValue', $event.target.value);open=true"
        @focus="profileId && !models.length ? discover(false) : (open=true)"
      >
      <button v-if="profileId" type="button" class="rounded-lg border border-slate-600 bg-slate-800 px-3 text-xs text-cyan-300 disabled:opacity-50" :disabled="loading" @click="discover(true)">{{ loading ? '读取中…' : '读取模型' }}</button>
    </div>
    <div v-if="open && filtered.length" class="absolute z-20 mt-1 max-h-52 w-full overflow-y-auto rounded-lg border border-slate-600 bg-slate-950 p-1 shadow-2xl">
      <button v-for="item in filtered" :key="item" type="button" class="block w-full rounded px-3 py-2 text-left text-xs text-slate-300 hover:bg-cyan-950 hover:text-cyan-200" @mousedown.prevent="choose(item)">{{ item }}</button>
    </div>
    <p v-if="message" class="mt-1 text-[10px] leading-relaxed text-slate-500">{{ message }}</p>
  </div>
</template>

<style scoped>
.connection-field { width:100%; border:1px solid rgb(51 65 85); border-radius:.5rem; background:rgb(15 23 42); padding:.6rem .7rem; color:rgb(226 232 240); font-size:.8rem; outline:none; }
.connection-field:focus { border-color:rgb(6 182 212); }
</style>
