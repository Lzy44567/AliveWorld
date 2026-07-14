export function buildCharacterImageContext(character = {}) {
  const memory = character.important_memories || character.memories || character.recent_memories || [];
  const memoryText = Array.isArray(memory) ? memory.slice(-8).join('；') : String(memory || '');
  return [
    character.description || character.desc || character.content || '',
    character.appearance ? `外观资料：${character.appearance}` : '',
    character.personality ? `性格资料：${character.personality}` : '',
    character.starting_scene ? `初始设定：${character.starting_scene}` : '',
    memoryText ? `重要记忆：${memoryText}` : '',
  ].filter(Boolean).join('\n');
}
