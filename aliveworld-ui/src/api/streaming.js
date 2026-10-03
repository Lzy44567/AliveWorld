const MAX_EVENT_LENGTH = 8 * 1024 * 1024;
export const UNKNOWN_OUTCOME = '流式连接中断，结果未确认。请重新载入核对保存状态；不会自动重发。可关闭流式后明确重试。';

// One request, one reader. The callback belongs to the initiating context,
// never to a component's mount lifetime. Only complete is authoritative.
export async function postEventStream(url, payload, onDelta = () => {}) {
  let reader;
  try {
    const response = await fetch(url, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `流式请求失败 (${response.status})。可关闭流式后明确重试。`);
    }
    if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
      throw new Error('服务器未返回流式响应；请重新载入核对结果，不会自动重发。');
    }
    reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8', { fatal: true });
    let buffer = '', event = '', dataLines = [], eventLength = 0, previewLength = 0;
    const dispatch = () => {
      const name = event;
      const raw = dataLines.join('\n');
      event = ''; dataLines = []; eventLength = 0;
      if (!raw || !['start', 'delta', 'complete', 'error'].includes(name)) return null;
      let data;
      try { data = JSON.parse(raw); } catch { throw new Error('流式事件格式错误；请重新载入核对结果，不会自动重发。'); }
      if (name === 'error') {
        throw new Error(`${data.message || '生成失败'}（不会自动重发；可关闭流式后明确重试）`);
      }
      if (name === 'delta') {
        if (typeof data.text !== 'string') throw new Error('流式正文格式错误；请重新载入核对结果。');
        previewLength += data.text.length;
        if (previewLength > MAX_EVENT_LENGTH) throw new Error('流式正文超出安全长度；请重新载入核对结果。');
        onDelta(data.text);
      }
      return name === 'complete' ? { data } : null;
    };
    while (true) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      if (buffer.length > MAX_EVENT_LENGTH) throw new Error('流式事件超出安全长度；请重新载入核对结果。');
      let end;
      while ((end = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, end).replace(/\r$/, '');
        buffer = buffer.slice(end + 1);
        if (!line) {
          const result = dispatch();
          if (result) return result.data;
        } else if (!line.startsWith(':')) {
          eventLength += line.length;
          if (eventLength > MAX_EVENT_LENGTH) throw new Error('流式事件超出安全长度；请重新载入核对结果。');
          const colon = line.indexOf(':');
          const field = colon < 0 ? line : line.slice(0, colon);
          const content = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '');
          if (field === 'event') event = content;
          if (field === 'data') dataLines.push(content);
        }
      }
      if (done) throw new Error(UNKNOWN_OUTCOME);
    }
  } catch (error) {
    if (error instanceof TypeError || error?.name === 'AbortError') throw new Error(UNKNOWN_OUTCOME);
    throw error;
  } finally {
    if (reader) {
      // Releasing the reader never aborts an in-flight context on view switches.
      await reader.cancel().catch(() => {});
      reader.releaseLock();
    }
  }
}
