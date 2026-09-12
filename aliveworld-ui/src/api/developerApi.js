const TOKEN_KEY = 'aw_developer_token';

function token() { return sessionStorage.getItem(TOKEN_KEY) || ''; }

async function payload(response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `开发者工具请求失败（HTTP ${response.status}）`);
  return body;
}

async function request(path, options = {}, authorized = false) {
  const headers = { ...(options.headers || {}) };
  if (options.body) headers['Content-Type'] = 'application/json';
  if (authorized && token()) headers.Authorization = `Bearer ${token()}`;
  return payload(await fetch(`/api/v1/developer${path}`, { ...options, headers, cache: 'no-store' }));
}

export const developerApi = {
  status: () => request('/status'),
  async setup(password) {
    const result = await request('/setup', { method: 'POST', body: JSON.stringify({ password }) });
    sessionStorage.setItem(TOKEN_KEY, result.token);
    return result;
  },
  async unlock(password) {
    const result = await request('/unlock', { method: 'POST', body: JSON.stringify({ password }) });
    sessionStorage.setItem(TOKEN_KEY, result.token);
    return result;
  },
  async lock() {
    await request('/lock', { method: 'POST' }, true).catch(() => null);
    sessionStorage.removeItem(TOKEN_KEY);
  },
  prompts: () => request('/prompts', {}, true),
  savePrompt: (id, content) => request(`/prompts/${encodeURIComponent(id)}`, {
    method: 'PUT', body: JSON.stringify({ content }),
  }, true),
  restorePrompt: id => request(`/prompts/${encodeURIComponent(id)}`, { method: 'DELETE' }, true),
};
