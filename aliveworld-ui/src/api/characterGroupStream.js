import { CharacterApiError } from './characterApiError.js';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const EVENTS = new Set(['ready', 'input_saved', 'state_changed', 'accepted', 'preview_start', 'preview_delta', 'preview_end', 'validating', 'group_saved', 'failed', 'cancelled', 'interrupted']);
const REQUEST_EVENTS = new Set(['accepted', 'preview_start', 'preview_delta', 'preview_end', 'validating', 'group_saved', 'cancelled', 'interrupted']);
const integer = value => Number.isSafeInteger(value) && value >= 0;
const invalid = () => new CharacterApiError('角色输出连接状态待核对，请重新读取会话；不会自动重发。');

// One subscription connection, not one model request. A terminal generation
// frame does not close this connection: queued batches may follow it.
export async function characterGroupStream(id, onEvent, { signal, fetchImpl = globalThis.fetch } = {}) {
  let reader;
  const detach = () => { if (reader) void reader.cancel().catch(() => {}); };
  try {
    const response = await fetchImpl('/api/v1/character-sessions/' + encodeURIComponent(id) + '/events',
      { headers: { Accept: 'text/event-stream' }, signal });
    if (!response.ok || !response.headers.get('content-type')?.includes('text/event-stream')) {
      const data = await response.json().catch(() => ({}));
      throw new CharacterApiError(data?.error?.message || '角色输出订阅失败', data?.error?.code || 'OUTCOME_UNKNOWN', data?.error?.retryable);
    }
    reader = response.body.getReader();
    signal?.addEventListener('abort', detach, { once: true });
    const decoder = new TextDecoder('utf-8', { fatal: true });
    let buffer = '', name = '', lines = [], bytes = 0, stream = '', sequence = 0;
    const dispatch = () => {
      const event = name, raw = lines.join('\n'); name = ''; lines = []; bytes = 0;
      if (!raw) return;
      let data;
      try { data = JSON.parse(raw); } catch { throw invalid(); }
      if (!data || Array.isArray(data) || typeof data !== 'object' || data.session_id !== id
          || !UUID.test(data.stream_id) || !integer(data.event_seq) || data.event_seq !== sequence + 1) throw invalid();
      if (!stream) {
        if (event !== 'ready' || data.event_seq !== 1 || !integer(data.revision)) throw invalid();
        stream = data.stream_id;
      } else if (data.stream_id !== stream || event === 'ready') throw invalid();
      sequence = data.event_seq;
      if (!EVENTS.has(event)) return;
      if (REQUEST_EVENTS.has(event) || data.request_id != null) {
        if (!UUID.test(data.action_id) || !UUID.test(data.request_id) || !UUID.test(data.group_id)
            || data.v !== 1 || !integer(data.seq) || data.seq < 1) throw invalid();
      }
      if (event.startsWith('preview_') && (!integer(data.ordinal) || data.ordinal > 5)) throw invalid();
      if (event === 'preview_delta' && typeof data.text !== 'string') throw invalid();
      if (event === 'accepted' && (!Array.isArray(data.reserved_ai_ids) || !data.reserved_ai_ids.length
          || data.reserved_ai_ids.length > 6 || new Set(data.reserved_ai_ids).size !== data.reserved_ai_ids.length
          || data.reserved_ai_ids.some(mid => !UUID.test(mid)))) throw invalid();
      onEvent(event, data);
    };
    while (!signal?.aborted) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      // Bound both unfinished lines and a complete multi-line frame in bytes.
      if (new TextEncoder().encode(buffer).length > 262144) throw invalid();
      let end;
      while ((end = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, end).replace(/\r$/, ''); buffer = buffer.slice(end + 1);
        if (!line) { dispatch(); continue; }
        if (line.startsWith(':')) continue;
        bytes += new TextEncoder().encode(line).length;
        if (bytes > 262144) throw invalid();
        const colon = line.indexOf(':'), field = colon < 0 ? line : line.slice(0, colon);
        const content = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '');
        if (field === 'event') name = content;
        if (field === 'data') lines.push(content);
      }
      if (done && !signal?.aborted) throw invalid();
    }
  } catch (error) {
    if (!signal?.aborted) throw error instanceof CharacterApiError ? error : invalid();
  } finally {
    signal?.removeEventListener('abort', detach);
    if (reader) { await reader.cancel().catch(() => {}); reader.releaseLock(); }
  }
}
