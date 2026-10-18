import { postEventStream } from './streaming.js';
const BASE_URL = '/api/v1/asset-workshops';

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || '资产工坊请求失败');
  return data;
}

const json = body => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body)
});

export const assetWorkshopApi = {
  saveBrief(id, text) { return request(`${BASE_URL}/${id}/creative-brief`, { ...json({ creative_brief: text }), method: 'PUT' }); },
  review(id, source, operationIds, accept) { return request(`${BASE_URL}/${id}/review`, json({ source, operation_ids: operationIds, accept })); },
  chatStream(id, message, mode, commitChanges, onDelta) { return postEventStream(`${BASE_URL}/${id}/chat/stream`, { message, mode, commit_changes: commitChanges }, onDelta); },
  start(assetType, assetName, sessionId = '') {
    return request(`${BASE_URL}/start`, json({
      asset_type: assetType, asset_name: assetName, session_id: sessionId
    }));
  },
  chat(id, message, mode, commitChanges = false) {
    return request(`${BASE_URL}/${id}/chat`, json({
      message, mode, commit_changes: commitChanges
    }));
  },
  operations(id, operations) {
    return request(`${BASE_URL}/${id}/operations`, json({ operations }));
  },
  undo(id) {
    return request(`${BASE_URL}/${id}/undo`, { method: 'POST' });
  },
  publish(id) {
    return request(`${BASE_URL}/${id}/publish`, { method: 'POST' });
  }
};
