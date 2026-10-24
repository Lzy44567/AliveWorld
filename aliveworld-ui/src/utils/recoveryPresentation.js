export const recoveryGuidance = {
  output_limit: '输出额度不足：可到设置 → 接口与模型 → 编辑接口 → 高级调整最大输出tokens。思考也可能消耗额度，提高上限可能增加费用。',
  format: '回复格式不完整：可先保留文字，再检查模型与提示词格式要求，修改原请求后明确重试。',
  connection: '传输未完成：检查网络与服务状态，再重新载入确认本次未保存后重试。',
  generation_or_save: '生成或保存未完成：请先重新载入核对故事或资产状态，再决定是否重试。',
};
export function recoveryExport(draft) {
  return `未完成残稿（不是正式故事或资产）\n${draft.created_at}\n${recoveryGuidance[draft.reason] || recoveryGuidance.generation_or_save}\n\n原请求：\n${draft.request}\n\n已收到的文字：\n${draft.text}\n`;
}
export function canRestoreRequest(current, original) {
  return !current.trim() || current === original;
}
