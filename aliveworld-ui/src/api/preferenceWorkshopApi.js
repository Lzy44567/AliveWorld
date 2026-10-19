import { postEventStream } from './streaming.js';
const BASE_URL = '/api/v1/preferences/workshops';

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
  saveBrief(id, text) { return request(`${BASE_URL}/${id}/creative-brief`, { ...json({ creative_brief: text }), method: 'PUT' }); },
  review(id, source, operationIds, accept) { return request(`${BASE_URL}/${id}/review`, json({ source, operation_ids: operationIds, accept })); },
  chatStream(id, message, mode, commitChanges, onDelta, generationId, useHistory = false) { return postEventStream(`${BASE_URL}/${id}/chat/stream`, { message, mode, commit_changes: commitChanges, generation_id: generationId, use_history: useHistory }, onDelta); },
  start(sessionId = '') { return request(`${BASE_URL}/start`, json({ session_id: sessionId })); },
  chat(id, message, mode, commitChanges = false, generationId, useHistory = false) {
    return request(`${BASE_URL}/${id}/chat`, json({ message, mode, commit_changes: commitChanges, generation_id: generationId, use_history: useHistory }));
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
