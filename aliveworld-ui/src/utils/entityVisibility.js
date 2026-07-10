export const ENTITY_VISIBILITIES = Object.freeze({
  hidden: 'hidden',
  names: 'names',
  motives: 'motives',
  full: 'full'
});

export function normalizeEntityVisibility(value) {
  return Object.values(ENTITY_VISIBILITIES).includes(value) ? value : ENTITY_VISIBILITIES.hidden;
}

export function projectLocalEntity(entity, visibility) {
  const mode = normalizeEntityVisibility(visibility);
  if (mode === ENTITY_VISIBILITIES.hidden) return null;

  const shared = {
    name: entity.name,
    is_active: entity.is_active,
    tags: ['本局实体']
  };
  if (mode === ENTITY_VISIBILITIES.names) {
    return { ...shared, desc: '暗流详情已隐藏' };
  }
  if (mode === ENTITY_VISIBILITIES.motives) {
    return { ...shared, desc: `动机：${entity.motive || entity.description || '未公开'}` };
  }

  return {
    ...entity,
    tags: Array.isArray(entity.tags) ? entity.tags : [],
    desc: entity.description || entity.motive || ''
  };
}

function getEntityName(content) {
  const match = String(content || '').match(/【([^】]+)】|\[([^\]]+)\]/);
  return match?.[1] || match?.[2] || '未知实体';
}

export function formatUndercurrentDebug(content, visibility, localEntities = []) {
  const mode = normalizeEntityVisibility(visibility);
  if (mode === ENTITY_VISIBILITIES.hidden) return '';

  const name = getEntityName(content);
  if (mode === ENTITY_VISIBILITIES.names) return `🌌 暗流变化：[${name}]`;
  if (mode === ENTITY_VISIBILITIES.motives) {
    const entity = localEntities.find(item => item.name === name);
    const motive = entity?.motive || entity?.description || '未公开';
    return `🌌 暗流变化：[${name}]（动机：${motive}）`;
  }
  return String(content || '');
}
