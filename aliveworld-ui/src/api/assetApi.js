// src/api/assetApi.js
const BASE_URL = "http://127.0.0.1:8000/api/v1/lobby";

export const assetApi = {
  async getAssets() {
    const res = await fetch(`${BASE_URL}/assets`);
    if (!res.ok) throw new Error("拉取资产失败");
    return await res.json();
  },

  async deleteSave(saveName) {
    const res = await fetch(`${BASE_URL}/saves/${encodeURIComponent(saveName)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error("档案删除失败");
    return await res.json();
  },

  async getSystemLogs() {
    const res = await fetch(`${BASE_URL}/logs`);
    if (!res.ok) throw new Error("拉取日志失败");
    return await res.json();
  },

  // === 以下为新增的万象工坊 CRUD 接口 ===

  async getAssetDetail(type, name) {
    const res = await fetch(`${BASE_URL}/assets/${type}/${encodeURIComponent(name)}`);
    if (!res.ok) throw new Error("获取资产详情失败");
    return await res.json();
  },

// 修改这个方法
  async saveAsset(type, name, yamlContent, parsedData = null, overwrite = false) {
    const res = await fetch(`${BASE_URL}/assets/${type}/${encodeURIComponent(name)}`, {
      method: 'POST',
      headers: { "Content-Type": "application/json" },
      // 同时把原代码和解析后的表单对象传过去
      body: JSON.stringify({ content: yamlContent, parsed_data: parsedData, overwrite })
    });
    if (!res.ok) throw new Error("保存资产失败");
    return await res.json();
  },

  async deleteAsset(type, name) {
    const res = await fetch(`${BASE_URL}/assets/${type}/${encodeURIComponent(name)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error("删除资产失败");
    return await res.json();
  },

  async lifecycleSave(saveName, action, newName) {
    const res = await fetch(`${BASE_URL}/saves/${encodeURIComponent(saveName)}/${action}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ new_name: newName })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `${action === 'clone' ? '克隆' : '重命名'}存档失败`);
    return data;
  },

  async lifecycleAsset(type, name, action, newName) {
    const res = await fetch(`${BASE_URL}/assets/${type}/${encodeURIComponent(name)}/${action}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ new_name: newName })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `${action === 'clone' ? '克隆' : '重命名'}失败`);
    return data;
  }
};
