const TYPES = { one_shot: '一次性', persistent: '持续性', evolving: '可演化' };
const STATUSES = { active: '生效中', consumed: '已消失', cancelled: '已取消' };
const CONSUME = { on_success: '触发后消失', on_attempt: '判断后消失', after_n: '触发 N 次后消失', never: '持续保留' };
const DEATH = { remove: '随来源消失', release: '来源死亡时释放', keep: '来源消失后保留' };
export const influenceTypeLabel = value => TYPES[value] || value || '未知类型';
export const influenceStatusLabel = value => STATUSES[value] || value || '未知状态';
export const consumePolicyLabel = value => CONSUME[value] || value || '未知规则';
export const sourceDeathLabel = value => DEATH[value] || value || '未知关联';
