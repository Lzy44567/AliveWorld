const id = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value);
const reasons = new Set(['explicit_preference','explicit_boundary','commitment','relationship_turn','goal_turn','conflict_repair']);
export const cognitionBasisLabels = Object.freeze({ author: '作者语境', player_statement: '对方明确说过', dialogue_event: '对话发生的事', model_inference: '角色推测或意图' });
export function characterCognition(value, session) {
  if (!value || value.version !== 1 || value.session_id !== session?.session_id || !Number.isSafeInteger(value.revision) || value.revision !== session.revision || !Array.isArray(value.entries) || value.entries.length > 128) return null;
  const participants = new Set((session.participants || []).map(p => p.instance_id));
  const ledger = new Map((session.ledger || []).map(e => [e.entry_id,e]));
  const entries = [], seen = new Set();
  for (const e of value.entries) {
    const original = ledger.get(e?.entry_id);
    if (!e || !id(e.entry_id) || seen.has(e.entry_id) || !original || !['knowledge','belief','intent','relationship','experience'].includes(e.kind) || e.kind !== original.kind || !Object.hasOwn(cognitionBasisLabels,e.basis) || e.basis !== original.source?.type || !(e.about_instance_id === null || participants.has(e.about_instance_id)) || (original.about_instance_id || null) !== e.about_instance_id || !id(e.root_entry_id) || !(e.supersedes_entry_id === null || id(e.supersedes_entry_id)) || (e.annotation_reason !== null && !reasons.has(e.annotation_reason))) return null;
    seen.add(e.entry_id);
    entries.push({ entry_id:e.entry_id, about_instance_id:e.about_instance_id, kind:e.kind, basis:e.basis, root_entry_id:e.root_entry_id, supersedes_entry_id:e.supersedes_entry_id, annotation_reason:e.annotation_reason });
  }
  return { version:1, session_id:value.session_id, revision:value.revision, entries };
}
export function sourceRecallReport(value) {
  if (!value || value.version !== 1 || !Array.isArray(value.entries) || value.entries.length > 32) return null;
  const entries = [], seen = new Set();
  for (const e of value.entries) {
    if (!e || !id(e.entry_id) || seen.has(e.entry_id) || !['sent','budget','limit'].includes(e.state)) return null;
    seen.add(e.entry_id); entries.push({entry_id:e.entry_id,state:e.state});
  }
  return {version:1,entries};
}
export function cognitionRows(report, session, basis = '', object = '') {
  if (!report || report.session_id !== session?.session_id || report.revision !== session.revision) return [];
  const ledger = new Map((session.ledger || []).map(e => [e.entry_id,e]));
  return report.entries.filter(e => (!basis || e.basis === basis) && (!object || (object === 'unspecified' ? e.about_instance_id === null : e.about_instance_id === object))).flatMap(e => ledger.has(e.entry_id) ? [{...e,content:ledger.get(e.entry_id).content}] : []);
}
