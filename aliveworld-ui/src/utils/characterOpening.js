// Only the complete validated v1 semantic fields are an explicit opening source.
export function cardOpening(card) {
  const fields = card?.role_fields;
  const limits = { description: 16000, personality: 8000, scenario: 8000, dialogue_examples: 8000, first_message: 8000 };
  if (!fields || fields.version !== 1 || Object.keys(fields).length !== 6) return '';
  let total = 0;
  for (const [key, limit] of Object.entries(limits)) {
    if (typeof fields[key] !== 'string' || Array.from(fields[key]).length > limit) return '';
    total += Array.from(fields[key]).length;
  }
  return total <= 32000 && fields.first_message.trim() ? fields.first_message : '';
}
