// src/api/gameApi.js
const BASE_URL = "http://127.0.0.1:8000/api/v1/game";

export const gameApi = {
  // 创世启航
  async startGame(payload) {
    const res = await fetch(`${BASE_URL}/start`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("创世失败");
    return await res.json();
  },

  // 读取旧档
  async loadGame(saveName) {
    const res = await fetch(`${BASE_URL}/load`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ save_name: saveName })
    });
    if (!res.ok) throw new Error("存档损坏或不存在");
    return await res.json();
  },

  // 玩家执行行动
  async processAction(sessionId, payload) {
    const res = await fetch(`${BASE_URL}/${sessionId}/action`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("推演失败");
    return await res.json();
  },

  // 撤回上一步
  async undoTurn(sessionId) {
    const res = await fetch(`${BASE_URL}/${sessionId}/undo`, { method: "POST" });
    if (!res.ok) throw new Error("无法撤回");
    return await res.json();
  },

  // 重试本回合
  async retryTurn(sessionId, payload) {
    const res = await fetch(`${BASE_URL}/${sessionId}/retry`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("重试失败");
    return await res.json();
  }
};