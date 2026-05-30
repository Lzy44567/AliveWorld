// src/api/assetApi.js
const BASE_URL = "http://127.0.0.1:8000/api/v1/lobby";

export const assetApi = {
  // 获取所有工坊资产(世界书、文风、角色、旧存档列表)
  async getAssets() {
    const res = await fetch(`${BASE_URL}/assets`);
    if (!res.ok) throw new Error("拉取资产失败");
    return await res.json();
  }
};