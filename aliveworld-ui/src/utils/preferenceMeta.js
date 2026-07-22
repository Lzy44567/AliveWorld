const INLINE_PATTERN = /\[\[\s*偏好\s*[：:]\s*([\s\S]*?)\]\]/g;

export function parsePreferenceMeta(input = '') {
  const raw = String(input || '').trim();
  const declarations = [];
  let action = raw.replace(INLINE_PATTERN, (_, text) => {
    const value = String(text || '').trim();
    if (value) declarations.push(value);
    return '';
  });
  const command = action.match(/^\/偏好(?:\s+|[：:])([\s\S]+)$/);
  if (command) {
    declarations.push(command[1].trim());
    action = '';
  }
  action = action.replace(/\n{3,}/g, '\n\n').trim();
  return { action, declarations: declarations.filter(Boolean) };
}

export function insertPreferenceBlock(current = '') {
  const prefix = String(current || '').trimEnd();
  return `${prefix}${prefix ? '\n\n' : ''}[[偏好：]]`;
}
