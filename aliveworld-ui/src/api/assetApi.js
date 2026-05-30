// src/api/assetApi.js
const BASE_URL = "http://127.0.0.1:8000/api/v1/lobby";

export const assetApi = {
  // 获取所有工坊资产(世界书、文风、角色、旧存档列表)
  async getAssets() {
    const res = await fetch(`${BASE_URL}/assets`);
    if (!res.ok) throw new Error("拉取资产失败");
    return await res.json();
  },

  // 彻底粉碎删除存档
  async deleteSave(saveName) {
    const res = await fetch(`${BASE_URL}/saves/${encodeURIComponent(saveName)}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error("档案删除失败");
    return await res.json();
  },

  // 获取后端实时运转日志
  async getSystemLogs() {
    const res = await fetch(`${BASE_URL}/logs`);
    if (!res.ok) throw new Error("拉取日志失败");
    return await res.json();
  }
};