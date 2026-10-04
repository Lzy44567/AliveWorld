// Request-scoped display metadata only; never copy message text or persist it.
export function characterWorldReport(value) {
  if (!value || value.window_turns !== 4 || !Array.isArray(value.entries) || value.entries.length > 16) return null;
  const countKeys = ['resident_count', 'omitted_by_limit', 'omitted_by_budget'];
  if (countKeys.some(key => !Number.isSafeInteger(value[key]) || value[key] < 0)) return null;
  const entries = [];
  for (const item of value.entries) {
    if (!item || typeof item.entry_id !== 'string' || Array.from(item.entry_id).length > 64 || typeof item.entry_name !== 'string' || Array.from(item.entry_name).length > 100 || !['current', 'recent'].includes(item.source) || !Number.isInteger(item.turn_distance) || item.turn_distance < 0 || item.turn_distance > 4 || (item.source === 'current') !== (item.turn_distance === 0) || typeof item.planned !== 'boolean') return null;
    entries.push({ entry_id: item.entry_id, entry_name: item.entry_name, source: item.source, turn_distance: item.turn_distance, planned: item.planned });
  }
  return { window_turns: 4, entries, ...Object.fromEntries(countKeys.map(key => [key, value[key]])) };
}
