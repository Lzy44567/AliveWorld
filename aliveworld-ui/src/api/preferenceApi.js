const API_URL = 'http://127.0.0.1:8000/api/v1/preferences';

async function parse(res, fallback) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || fallback);
  return data;
}

export const preferenceApi = {
  async list() {
    return parse(await fetch(API_URL), '读取用户偏好失败');
  },
  async update(id, updates) {
    return parse(await fetch(`${API_URL}/${encodeURIComponent(id)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ updates })
    }), '更新用户偏好失败');
  },
  async remove(id) {
    return parse(await fetch(`${API_URL}/${encodeURIComponent(id)}`, { method: 'DELETE' }), '删除用户偏好失败');
  },
  async declare(text, sessionId = '', options = {}) {
    return parse(await fetch(`${API_URL}/declare`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text, session_id: sessionId,
        category: options.category || 'other',
        polarity: options.polarity || 'prefer',
        sensitive: Boolean(options.sensitive)
      })
    }), '记录用户偏好失败');
  },
  async analyze(sessionId, force = true) {
    return parse(await fetch(`${API_URL}/analyze`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, force })
    }), '分析用户偏好失败');
  }
};
