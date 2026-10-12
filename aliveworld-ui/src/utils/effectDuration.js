export function effectDurationLabel(effect) {
  if (!(effect.duration > 0)) return '';
  if (!(effect.tick_seconds > 0)) return `剩${effect.duration}轮`;
  const seconds = Math.max(0, effect.duration * effect.tick_seconds - (effect.tick_elapsed || 0));
  if (seconds < 60) return `剩${seconds}秒`;
  const minutes = Math.floor(seconds / 60);
  return `剩${minutes}分${seconds % 60 ? `${seconds % 60}秒` : ''}`;
}
