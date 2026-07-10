function toTextLines(value) {
  if (Array.isArray(value)) return value.map(item => typeof item === 'string' ? item : JSON.stringify(item)).join('\n');
  return value ? String(value) : '';
}

function toPrettyJson(value, fallback) {
  return JSON.stringify(value ?? fallback, null, 2);
}

function parseLines(value) {
  return String(value || '').split('\n').map(line => line.trim()).filter(Boolean);
}

function parseJson(value, expectedType, label) {
  try {
    const parsed = JSON.parse(value || (expectedType === 'array' ? '[]' : '{}'));
    if (expectedType === 'array' && !Array.isArray(parsed)) throw new Error();
    if (expectedType === 'object' && (!parsed || Array.isArray(parsed) || typeof parsed !== 'object')) throw new Error();
    return parsed;
  } catch {
    throw new Error(`${label}必须是有效的 ${expectedType === 'array' ? 'JSON 数组' : 'JSON 对象'}`);
  }
}

export function createEntityEditorForm(asset = {}) {
  return {
    desc: asset.description || '',
    motive: asset.motive || asset.description || '',
    status: asset.status || '',
    recentActionsText: toTextLines(asset.recent_actions),
    plansText: toTextLines(asset.plans),
    mechanismsText: toTextLines(asset.mechanisms),
    triggersJson: toPrettyJson(asset.triggers, []),
    relationshipsJson: toPrettyJson(asset.relationships, {}),
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
    triggers: parseJson(form.triggersJson, 'array', '触发器'),
    relationships: parseJson(form.relationshipsJson, 'object', '关系'),
    importance
  };
}
