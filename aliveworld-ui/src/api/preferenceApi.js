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
  }
};
