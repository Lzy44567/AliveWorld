export const roleFieldSpecs = [
  ['description', '背景与外观设定', 16000], ['personality', '性格与行为倾向', 8000],
  ['scenario', '初始情景', 8000], ['dialogue_examples', '行为与对话示例', 8000], ['first_message', '角色卡开场', 8000],
];
export function structuredDraft(description = '', scenario = '') {
  return { version: 1, description, personality: '', scenario, dialogue_examples: '', first_message: '' };
}
export function compatibleRoleText(fields) {
  const parts = fields.description ? [fields.description] : [];
  for (const [key, label] of [['personality', '性格'], ['scenario', '场景设定'], ['dialogue_examples', '对话示例']]) if (fields[key]) parts.push(`【${label}】\n${fields[key]}`);
  return parts.join('\n\n');
}
export function roleFieldsError(fields) {
  if (!fields || fields.version !== 1 || Object.keys(fields).length !== 6) return '独立字段格式不完整';
  let total = 0;
  for (const [key, label, limit] of roleFieldSpecs) {
    if (typeof fields[key] !== 'string') return `${label}必须是文本`;
    const count = Array.from(fields[key]).length; total += count;
    if (count > limit) return `${label}超过${limit}字符；请自行分配或缩减，不会截断`;
  }
  return total > 32000 || Array.from(compatibleRoleText(fields)).length > 32000 ? '独立字段或合并描述超过32000字符' : '';
}
