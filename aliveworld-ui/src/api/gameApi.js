// src/api/gameApi.js
const API_URL = "http://127.0.0.1:8000/api/v1/game";

export const gameApi = {
  async startGame(payload) {
    const res = await fetch(`${API_URL}/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!res.ok) throw new Error("启动失败");
    return res.json();
  },
  async loadGame(saveName) {
    const res = await fetch(`${API_URL}/load`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ save_name: saveName }) });
    if (!res.ok) throw new Error("载入失败");
    return res.json();
  },
  async processAction(sessionId, payload) {
    const res = await fetch(`${API_URL}/${sessionId}/action`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!res.ok) throw new Error("推演失败");
    return res.json();
  },
  async undoTurn(sessionId) {
    const res = await fetch(`${API_URL}/${sessionId}/undo`, { method: 'POST' });
    if (!res.ok) throw new Error("撤回失败");
    return res.json();
  },
  async retryTurn(sessionId, payload) {
    const res = await fetch(`${API_URL}/${sessionId}/retry`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!res.ok) throw new Error("重试失败");
    return res.json();
  },
  // 🚀 新增：专门为了“重掷未来”开辟的端点
  async rerollTurn(sessionId, payload) {
    const res = await fetch(`${API_URL}/${sessionId}/reroll`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!res.ok) throw new Error("重掷失败");
    return res.json();
  },
  async pullAsset(sessionId, payload) {
    const res = await fetch(`${API_URL}/${sessionId}/pull_asset`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!res.ok) throw new Error("拉取失败");
    return res.json();
  },
  async updateLocalAsset(sessionId, assetType, assetName, payload) {
    const res = await fetch(`${API_URL}/${sessionId}/assets/${assetType}/${assetName}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ parsed_data: payload }) });
    if (!res.ok) throw new Error("更新失败");
    return res.json();
  },
  async deleteLocalAsset(sessionId, assetType, assetName) {
    const res = await fetch(`${API_URL}/${sessionId}/assets/${assetType}/${assetName}`, { method: 'DELETE' });
    if (!res.ok) throw new Error("删除失败");
    return res.json();
  }
};
