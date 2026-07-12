const BASE_URL = "http://127.0.0.1:8000/api/v1/worldbooks/workshops";

const request = async (url, options = {}) => {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || '世界书工坊请求失败');
  return data;
};

export const worldbookWorkshopApi = {
  start(worldbookName) {
    return request(`${BASE_URL}/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ worldbook_name: worldbookName }) });
  },
  chat(id, message, mode) {
    return request(`${BASE_URL}/${id}/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message, mode }) });
  },
  approve(id, operationId) {
    return request(`${BASE_URL}/${id}/pending/${operationId}/approve`, { method: 'POST' });
  },
  reject(id, operationId) {
    return request(`${BASE_URL}/${id}/pending/${operationId}`, { method: 'DELETE' });
  },
  undo(id) {
    return request(`${BASE_URL}/${id}/undo`, { method: 'POST' });
  },
  publish(id, worldbookName = null) {
    return request(`${BASE_URL}/${id}/publish`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ worldbook_name: worldbookName }) });
  },
};
