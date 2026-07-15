const BASE_URL = "http://127.0.0.1:8000/api/v1/worldbooks/workshops";

const request = async (url, options = {}) => {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || '世界书工坊请求失败');
  return data;
};

export const worldbookWorkshopApi = {
  embeddingStatus() { return request(`${BASE_URL}/embeddings/status`); },
  downloadEmbeddings() { return request(`${BASE_URL}/embeddings/download`, { method: 'POST' }); },
  pauseEmbeddings() { return request(`${BASE_URL}/embeddings/pause`, { method: 'POST' }); },
  uninstallEmbeddings() { return request(`${BASE_URL}/embeddings/model`, { method: 'DELETE' }); },
  toggleEmbeddings(enabled) { return request(`${BASE_URL}/embeddings/toggle`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled }) }); },
  start(worldbookName, sessionId = null) {
    return request(`${BASE_URL}/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ worldbook_name: worldbookName, session_id: sessionId }) });
  },
  chat(id, message, mode, commitChanges = false) {
    return request(`${BASE_URL}/${id}/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message, mode, commit_changes: commitChanges }) });
  },
  operations(id, operations, confirmHighRisk = true) {
    return request(`${BASE_URL}/${id}/operations`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operations, confirm_high_risk: confirmHighRisk }) });
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
