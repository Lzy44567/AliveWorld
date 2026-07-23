const BASE_URL = 'http://127.0.0.1:8000/api/v1/preferences/workshops';

async function request(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || '偏好工坊请求失败');
  return data;
}

const json = body => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body)
});

export const preferenceWorkshopApi = {
  start(sessionId = '') { return request(`${BASE_URL}/start`, json({ session_id: sessionId })); },
  chat(id, message, mode, commitChanges = false) {
    return request(`${BASE_URL}/${id}/chat`, json({ message, mode, commit_changes: commitChanges }));
  },
  operations(id, operations, confirmHighRisk = true) {
    return request(`${BASE_URL}/${id}/operations`, json({ operations, confirm_high_risk: confirmHighRisk }));
  },
  approve(id, operationId) {
    return request(`${BASE_URL}/${id}/pending/${operationId}/approve`, { method: 'POST' });
  },
  reject(id, operationId) {
    return request(`${BASE_URL}/${id}/pending/${operationId}`, { method: 'DELETE' });
  },
  undo(id) { return request(`${BASE_URL}/${id}/undo`, { method: 'POST' }); },
  publish(id) { return request(`${BASE_URL}/${id}/publish`, { method: 'POST' }); }
};
