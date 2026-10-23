export const MAX_CONFLICT_BATCH = 100;
export function pendingConflictIds(records) {
  return records.filter(item => item.current && item.status === 'pending').slice(0, MAX_CONFLICT_BATCH).map(item => item.id);
}
export function selectedConflictIds(records, selected) {
  const valid = new Set(records.filter(item => item.current).map(item => item.id));
  return [...new Set(selected)].filter(id => valid.has(id)).slice(0, MAX_CONFLICT_BATCH);
}
