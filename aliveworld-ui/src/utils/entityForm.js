function toTextLines(value) {
  if (Array.isArray(value)) return value.map(item => typeof item === 'string' ? item : JSON.stringify(item)).join('\n');
  return value ? String(value) : '';
}

function parseLines(value) {
  return String(value || '').split('\n').map(line => line.trim()).filter(Boolean);
}

function toTriggerRows(value) {
  return (Array.isArray(value) ? value : []).map(trigger => ({
    condition: typeof trigger === 'object' ? String(trigger.condition || '') : String(trigger || ''),
    result: typeof trigger === 'object' ? String(trigger.result || '') : ''
  }));
}

function toRelationshipRows(value) {
  return Object.entries(value && typeof value === 'object' && !Array.isArray(value) ? value : {}).map(([target, relation]) => ({
    target,
    relation: String(relation || '')
  }));
}

export function createEntityEditorForm(asset = {}) {
  return {
    desc: asset.description || '',
    motive: asset.motive || asset.description || '',
    status: asset.status || '',
    recentActionsText: toTextLines(asset.recent_actions),
    plansText: toTextLines(asset.plans),
    mechanismsText: toTextLines(asset.mechanisms),
    triggers: toTriggerRows(asset.triggers),
    relationships: toRelationshipRows(asset.relationships),
    importance: asset.importance ?? 0.5
  };
}

export function buildEntityPayload(form) {
  const importance = Number(form.importance);
  if (!Number.isFinite(importance) || importance < 0 || importance > 1) {
    throw new Error('重要性必须是 0 到 1 之间的数字');
  }

  return {
    description: String(form.desc || ''),
    motive: String(form.motive || form.desc || ''),
    status: String(form.status || ''),
    recent_actions: parseLines(form.recentActionsText),
    plans: parseLines(form.plansText),
    mechanisms: parseLines(form.mechanismsText),
    triggers: (form.triggers || []).filter(row => row.condition || row.result).map(row => ({
      condition: String(row.condition || ''),
      result: String(row.result || '')
    })),
    relationships: Object.fromEntries((form.relationships || [])
      .filter(row => row.target && row.relation)
      .map(row => [String(row.target), String(row.relation)])),
    importance
  };
}
