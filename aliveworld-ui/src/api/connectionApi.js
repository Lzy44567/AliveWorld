const BASE_URL = '/api/v1/model-connections';

async function request(path = '', options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || '接口配置请求失败');
  return data;
}

const jsonOptions = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const connectionApi = {
  list: () => request(),
  create: payload => request('/profiles', jsonOptions('POST', payload)),
  update: (id, payload) => request(`/profiles/${encodeURIComponent(id)}`, jsonOptions('POST', payload)),
  clone: (id, name) => request(`/profiles/${encodeURIComponent(id)}/clone`, jsonOptions('POST', { name })),
  remove: id => request(`/profiles/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  reveal: id => request(`/profiles/${encodeURIComponent(id)}/reveal-secret`, { method: 'POST' }),
  test: id => request(`/profiles/${encodeURIComponent(id)}/test`, { method: 'POST' }),
  setRoute: (task, payload) => request(`/routes/${encodeURIComponent(task)}`, jsonOptions('POST', payload)),
};
