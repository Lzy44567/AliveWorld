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
    if (!res.ok) {
      const payload = await res.json().catch(() => ({}));
      throw new Error(payload.detail || "推演失败，本回合未保存。");
    }
    return res.json();
  },
  async updateStoryConfig(sessionId, payload) {
    const res = await fetch(`${API_URL}/${sessionId}/story_config`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!res.ok) throw new Error("局内设置保存失败");
    return res.json();
  },
  async getStoryMemory(sessionId) {
    const res = await fetch(`${API_URL}/${sessionId}/story-memory`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "读取故事记忆状态失败");
    return data;
  },
  async compactStoryMemory(sessionId, force = false) {
    const res = await fetch(`${API_URL}/${sessionId}/story-memory/compact`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ force })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "故事记忆压缩失败");
    return data;
  },
  async getCausalLedger(sessionId) {
    const res = await fetch(`${API_URL}/${sessionId}/causal-ledger`);
    if (!res.ok) throw new Error("读取暗流因果账本失败");
    return res.json();
  },
  async createInfluence(sessionId, data) {
    const res = await fetch(`${API_URL}/${sessionId}/causal-ledger`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ data }) });
    if (!res.ok) throw new Error("创建暗流影响失败");
    return res.json();
  },
  async updateInfluence(sessionId, influenceId, data) {
    const res = await fetch(`${API_URL}/${sessionId}/causal-ledger/${encodeURIComponent(influenceId)}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ data }) });
    if (!res.ok) throw new Error("更新暗流影响失败");
    return res.json();
  },
  async deleteInfluence(sessionId, influenceId) {
    const res = await fetch(`${API_URL}/${sessionId}/causal-ledger/${encodeURIComponent(influenceId)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error("删除暗流影响失败");
    return res.json();
  },
  async restoreInfluence(sessionId, influenceId) {
    const res = await fetch(`${API_URL}/${sessionId}/causal-ledger/${encodeURIComponent(influenceId)}/restore`, { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "恢复暗流影响失败");
    return data;
  },
  async purgeInfluence(sessionId, influenceId) {
    const res = await fetch(`${API_URL}/${sessionId}/causal-ledger/${encodeURIComponent(influenceId)}/purge`, { method: 'DELETE' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "永久删除暗流影响失败");
    return data;
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
  },
  async lifecycleLocalAsset(sessionId, assetType, assetName, action, newName) {
    const res = await fetch(`${API_URL}/${sessionId}/assets/${assetType}/${encodeURIComponent(assetName)}/${action}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ new_name: newName })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `${action === 'clone' ? '克隆' : '重命名'}失败`);
    return data;
  }
};
