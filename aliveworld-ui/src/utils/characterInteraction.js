const KEY = 'aw_character_interaction_v1';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const defaults = () => ({ delivery: 'stream', sendKey: 'enter' });
const valid = p => p && ['stream', 'non_stream'].includes(p.delivery) && ['enter', 'ctrl_enter'].includes(p.sendKey);
const deliveryFor = mode => mode === 'stream' ? 'stream' : 'non_stream';
const validDisplay = p => ['stream', 'gaps', 'instant'].includes(p.displayMode) && p.delivery === deliveryFor(p.displayMode);

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
      if (![1, 2].includes(data.version) || !data.entries || Array.isArray(data.entries) || typeof data.entries !== 'object' || Object.keys(data.entries).length > 2000) throw Error();
      for (const [id, p] of Object.entries(data.entries)) {
        if (!UUID.test(id) || !valid(p) || data.version === 2 && !validDisplay(p)) throw Error();
        entries[id] = { delivery: p.delivery, sendKey: p.sendKey,
          displayMode: data.version === 1 ? (p.delivery === 'stream' ? 'stream' : 'instant') : p.displayMode };
      }
    }
  } catch { entries = {}; writable = false; warning = '聊天交互设置无法读取，使用默认设置；原数据未覆盖。'; }
  return {
    entries, warning, writable,
    get(id) { const p = this.entries[id] || defaults(); return { delivery: p.delivery, sendKey: p.sendKey }; },
    display(id) { return this.entries[id]?.displayMode || 'stream'; },
    save() {
      if (!this.writable) return;
      try {
        if (!storage) throw Error();
        storage.setItem(KEY, JSON.stringify({ version: 2, entries: this.entries }));
        this.warning = '';
      } catch { this.warning = '聊天交互设置仅保存在本次运行；对话记录不受影响。'; }
    },
    set(id, changes) {
      if (!changes || typeof changes !== 'object' || Array.isArray(changes)) return false;
      const value = { ...this.get(id), displayMode: this.display(id), ...changes };
      if ('displayMode' in changes && !('delivery' in changes)) value.delivery = deliveryFor(changes.displayMode);
      if ('delivery' in changes && !('displayMode' in changes)) value.displayMode = changes.delivery === 'stream' ? 'stream' : 'instant';
      if (!UUID.test(id) || !valid(value) || !validDisplay(value) || Object.keys(changes).some(k => !['delivery', 'sendKey', 'displayMode'].includes(k))) return false;
      if (!this.entries[id] && Object.keys(this.entries).length >= 2000) { this.warning = '交互设置达到本机容量上限，未覆盖已有设置。'; return false; }
      this.entries[id] = value; this.save(); return true;
    },
    toggleDisplay(id, kind, enabled) {
      if (!['stream', 'gaps'].includes(kind) || typeof enabled !== 'boolean') return false;
      const current = this.display(id);
      return this.set(id, { displayMode: enabled ? kind : current === kind ? 'instant' : current });
    },
    remove(id) { delete this.entries[id]; this.save(); },
  };
}
