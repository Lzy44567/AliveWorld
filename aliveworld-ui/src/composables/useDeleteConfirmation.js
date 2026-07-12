import { onBeforeUnmount, ref } from 'vue';

export function useDeleteConfirmation(timeoutMs = 6000) {
  const confirmDeleteId = ref(null);
  let timer = null;
  const cancelDelete = () => {
    confirmDeleteId.value = null;
    if (timer) window.clearTimeout(timer);
    timer = null;
  };
  const requestDelete = (id) => {
    cancelDelete();
    confirmDeleteId.value = id;
    timer = window.setTimeout(cancelDelete, timeoutMs);
  };
  onBeforeUnmount(cancelDelete);
  return { confirmDeleteId, requestDelete, cancelDelete };
}
