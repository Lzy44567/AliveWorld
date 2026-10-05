// Stores identities only; malformed or unavailable persistence suppresses notices.
const KEY = 'aliveworld.character-memory-notices.v1';
const LIMIT = 256;
export function createMemoryNoticeCache(storage) {
  let backend, disabled = false, ids = [];
  try {
    backend = storage === undefined ? globalThis.localStorage : storage;
    if (!backend?.getItem || !backend?.setItem) disabled = true;
    else {
      const raw = backend.getItem(KEY);
      if (raw !== null) {
        const parsed = JSON.parse(raw);
        if (!parsed || parsed.version !== 1 || !Array.isArray(parsed.ids) || parsed.ids.length > LIMIT || parsed.ids.some(i => typeof i !== 'string' || i.length > 180) || new Set(parsed.ids).size !== parsed.ids.length) disabled = true;
        else ids = parsed.ids;
      }
    }
  } catch { disabled = true; }
  return {
    claim(sessionId, actionId) {
      const key = `${sessionId}:${actionId}`;
      if (disabled || typeof sessionId !== 'string' || !sessionId || key.length > 180 || ids.includes(key)) return false;
      const next = [...ids, key].slice(-LIMIT);
      try { backend.setItem(KEY, JSON.stringify({ version: 1, ids: next })); ids = next; return true; }
      catch { disabled = true; return false; }
    },
    removeSession(sessionId) {
      if (disabled) return;
      ids = ids.filter(i => !i.startsWith(`${sessionId}:`));
      try { backend.setItem(KEY, JSON.stringify({ version: 1, ids })); } catch { disabled = true; }
    },
  };
}
