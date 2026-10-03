const KEY = 'aw_character_interaction_v1';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const defaults = () => ({ delivery: 'stream', sendKey: 'enter' });
const valid = p => p && ['stream', 'non_stream'].includes(p.delivery) && ['enter', 'ctrl_enter'].includes(p.sendKey);

export function shouldSendCharacterKey(event, sendKey = 'enter', composing = false) {
  return event.key === 'Enter' && !composing && !event.isComposing && event.keyCode !== 229
    && !event.repeat && !event.shiftKey && !event.altKey
    && (event.ctrlKey || event.metaKey || sendKey === 'enter');
}

export function createCharacterInteractionPreferences(storage) {
  let entries = {}, writable = true, warning = '';
  try {
    if (storage === undefined) storage = globalThis.localStorage;
    const raw = storage?.getItem(KEY);
    if (raw) {
      if (new TextEncoder().encode(raw).length > 262144) throw Error();
      const data = JSON.parse(raw);
      if (data.version !== 1 || !data.entries || Array.isArray(data.entries) || typeof data.entries !== 'object' || Object.keys(data.entries).length > 2000) throw Error();
      for (const [id, p] of Object.entries(data.entries)) {
        if (!UUID.test(id) || !valid(p)) throw Error();
        entries[id] = { delivery: p.delivery, sendKey: p.sendKey };
      }
    }
  } catch { entries = {}; writable = false; warning = '聊天交互设置无法读取，使用默认设置；原数据未覆盖。'; }
  return {
    entries, warning, writable,
    get(id) { return { ...(this.entries[id] || defaults()) }; },
    save() {
      if (!this.writable) return;
      try {
        if (!storage) throw Error();
        storage.setItem(KEY, JSON.stringify({ version: 1, entries: this.entries }));
        this.warning = '';
      } catch { this.warning = '聊天交互设置仅保存在本次运行；对话记录不受影响。'; }
    },
    set(id, changes) {
      const value = { ...this.get(id), ...changes };
      if (!UUID.test(id) || !valid(value) || Object.keys(changes).some(k => !['delivery', 'sendKey'].includes(k))) return false;
      if (!this.entries[id] && Object.keys(this.entries).length >= 2000) { this.warning = '交互设置达到本机容量上限，未覆盖已有设置。'; return false; }
      this.entries[id] = value; this.save(); return true;
    },
    remove(id) { delete this.entries[id]; this.save(); },
  };
}
