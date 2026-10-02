export const promptModes = [
  { id: 'game', label: '游戏' }, { id: 'character', label: '角色' },
  { id: 'workshop', label: '工坊' }, { id: 'general', label: '通用' },
];

export function promptMode(task = '') {
  if (task.startsWith('story.') || task === 'world.capture' || task === 'undercurrent') return 'game';
  if (task === 'character' || task.startsWith('character.')) return 'character';
  if (task === 'workshop' || task.startsWith('workshop.')) return 'workshop';
  return 'general';
}

export const visiblePrompts = (slices, mode) => slices.filter(item => promptMode(item.task) === mode);

export function groupPrompts(slices) {
  return slices.reduce((out, item) => ((out[item.task] ||= []).push(item), out), {});
}
