export function normalizeEntityDisclosure(settings = {}) {
  const showMotives = Boolean(settings.showEntityMotives ?? settings.showMotives);
  const allowEditing = Boolean(settings.allowEntityEditing ?? settings.allowEditing);
  return {
    showNames: Boolean(settings.showEntityNames ?? settings.showNames) || showMotives || allowEditing,
    showMotives,
    allowEditing,
    showBubbles: Boolean(settings.showEntityBubbles ?? settings.showBubbles)
  };
}

export function projectLocalEntity(entity, disclosure) {
  const permissions = normalizeEntityDisclosure(disclosure);
  if (!permissions.showNames) return null;

  const shared = {
    name: entity.name,
    is_active: entity.is_active,
    tags: ['本局实体']
  };
  if (permissions.allowEditing) {
    return { ...entity, ...shared, desc: `动机：${entity.motive || entity.description || '未公开'}` };
  }
  if (!permissions.showMotives) {
    return { ...shared, desc: '暗流详情已隐藏' };
  }
  return { ...shared, desc: `动机：${entity.motive || entity.description || '未公开'}` };
}

function getEntityName(content) {
  const match = String(content || '').match(/【([^】]+)】|\[([^\]]+)\]/);
  return match?.[1] || match?.[2] || '未知实体';
}

export function formatUndercurrentDebug(content, disclosure, localEntities = []) {
  const permissions = normalizeEntityDisclosure(disclosure);
  if (!permissions.showBubbles || !permissions.showNames) return '';

  const name = getEntityName(content);
  if (permissions.showMotives) {
    const entity = localEntities.find(item => item.name === name);
    const motive = entity?.motive || entity?.description || '未公开';
    return `🌌 暗流变化：[${name}]（动机：${motive}）`;
  }
  return `🌌 暗流变化：[${name}]`;
}
