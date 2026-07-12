import { onBeforeUnmount, onMounted, ref } from 'vue';

export function useDeleteConfirmation() {
  const confirmDeleteId = ref(null);
  const cancelDelete = () => {
    confirmDeleteId.value = null;
  };
  const requestDelete = (id) => {
    confirmDeleteId.value = id;
  };
  const handleOutsidePointer = (event) => {
    if (confirmDeleteId.value === null) return;
    const area = event.target.closest?.('[data-delete-confirm-id]');
    if (!area || area.dataset.deleteConfirmId !== String(confirmDeleteId.value)) cancelDelete();
  };
  onMounted(() => document.addEventListener('pointerdown', handleOutsidePointer, true));
  onBeforeUnmount(() => document.removeEventListener('pointerdown', handleOutsidePointer, true));
  return { confirmDeleteId, requestDelete, cancelDelete };
}
