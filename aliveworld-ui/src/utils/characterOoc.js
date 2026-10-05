// Input identity is structural; parentheses and role text are never parsed as OOC.
export const oocText = value => typeof value === 'string' ? value.trim() : '';
export const oocLength = value => Array.from(oocText(value)).length;
export function oocError(value) {
  if (typeof value !== 'string') return '场外提示格式不正确。';
  if (oocLength(value) > 1000) return '场外提示最多1000字，请缩短后发送。';
  if (Array.from(value).some(char => char.length === 1 && char.charCodeAt(0) >= 0xd800 && char.charCodeAt(0) <= 0xdfff)) return '场外提示包含无效字符。';
  return '';
}
export function restoreInputPair(ctx, dialogue, note = '') {
  if (ctx.draft || ctx.oocDraft) return false;
  ctx.draft = dialogue || ''; ctx.oocDraft = note || '';
  if (ctx.oocDraft) ctx.oocOpen = true;
  return true;
}
