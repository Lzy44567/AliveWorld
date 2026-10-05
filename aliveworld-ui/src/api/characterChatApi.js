const BASE = '/api/v1/character-sessions';
const TERMINAL = new Set(['committed', 'failed', 'cancelled']);
export class CharacterApiError extends Error {
  constructor(message, code = 'OUTCOME_UNKNOWN', retryable = false) {
    super(message); this.code = code; this.retryable = retryable;
  }
}
async function request(path = '', method = 'GET', payload) {
  const response = await fetch(BASE + path, { method, headers: { 'Content-Type': 'application/json' }, ...(payload === undefined ? {} : { body: JSON.stringify(payload) }) });
  const data = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) throw new CharacterApiError(data?.error?.message || '角色会话请求失败', data?.error?.code || 'REQUEST_FAILED', data?.error?.retryable);
  return data;
}
// Character event names and identity rules intentionally differ from story SSE.
export async function characterStream(path, payload, onEvent) {
  const response = await fetch(BASE + path, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' }, body: JSON.stringify(payload) });
  if (!response.headers.get('content-type')?.includes('text/event-stream')) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new CharacterApiError(data?.error?.message || '角色会话请求失败', data?.error?.code || 'REQUEST_FAILED', data?.error?.retryable);
    return data;
  }
  const reader = response.body.getReader(), decoder = new TextDecoder('utf-8', { fatal: true });
  let buffer = '', name = '', lines = [], length = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      if (buffer.length > 262144) throw new CharacterApiError('流式事件超出安全长度');
      let end;
      while ((end = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, end).replace(/\r$/, ''); buffer = buffer.slice(end + 1);
        if (!line) {
          const event = name, raw = lines.join('\n'); name = ''; lines = []; length = 0;
          if (!raw || !['accepted', 'reply_delta', 'validating', ...TERMINAL].includes(event)) continue;
          let data;
          try { data = JSON.parse(raw); } catch { throw new CharacterApiError('流式事件格式错误，状态待确认'); }
          const accepted = onEvent(event, data);
          if (TERMINAL.has(event) && accepted !== false) return { ...data, status: event };
        } else if (!line.startsWith(':')) {
          length += line.length;
          if (length > 262144) throw new CharacterApiError('流式事件超出安全长度');
          const colon = line.indexOf(':'), field = colon < 0 ? line : line.slice(0, colon), content = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '');
          if (field === 'event') name = content;
          if (field === 'data') lines.push(content);
        }
      }
      if (done) throw new CharacterApiError('连接中断，状态待确认；不会自动重发');
    }
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}
const sid = id => '/' + encodeURIComponent(id);
export const characterChatApi = {
  list: cursor => request('?' + new URLSearchParams({ view: 'summary', ...(cursor ? { cursor } : {}) })),
  ledger: (id, view = 'public') => request(sid(id) + '/ledger?' + new URLSearchParams({ view })),
  get: id => request(sid(id)),
  create: payload => request('', 'POST', payload),
  update: (id, payload) => request(sid(id), 'PATCH', payload),
  markMemory: (id, payload) => request(sid(id) + '/memory/important', 'PUT', payload),
  enableAutomaticMemory: (id, payload) => request(sid(id) + '/memory/automatic', 'PUT', payload),
  selectAutomaticMemory: (id, payload) => request(sid(id) + '/memory/automatic-selection', 'PUT', payload),
  releaseAutomaticMemory: (id, payload) => request(sid(id) + '/memory/automatic-selection/release', 'POST', payload),
  acknowledgeMemoryNotice: (id, payload) => request(sid(id) + '/memory/notice-ack', 'PUT', payload),
  memorySources: (id, entry) => request(sid(id) + '/memory/' + encodeURIComponent(entry) + '/sources'),
  remove: (id, revision) => request(sid(id), 'DELETE', { expected_revision: revision }),
  turns: (id, before) => request(sid(id) + '/turns?' + new URLSearchParams({ limit: '50', ...(before ? { before } : {}) })),
  actionStatus: (id, action) => request(sid(id) + '/actions/' + encodeURIComponent(action)),
  action: (id, payload, callback) => payload.delivery === 'stream' ? characterStream(sid(id) + '/actions', payload, callback) : request(sid(id) + '/actions', 'POST', payload),
  retry: (id, action, payload, callback) => payload.delivery === 'stream' ? characterStream(sid(id) + '/actions/' + encodeURIComponent(action) + '/retry', payload, callback) : request(sid(id) + '/actions/' + encodeURIComponent(action) + '/retry', 'POST', payload),
  cancel: (id, requestId) => request(sid(id) + '/requests/' + encodeURIComponent(requestId) + '/cancel', 'POST', {}),
};
