const BASE_URL = '/api/v1/world-packages';

async function requireOk(response, fallback) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || fallback);
  return data;
}

async function sendFile(path, file) {
  const response = await fetch(`${BASE_URL}/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/octet-stream' },
    body: file,
  });
  return requireOk(response, '世界包文件处理失败');
}

export const worldPackageApi = {
  async list() {
    return requireOk(await fetch(BASE_URL), '读取世界包失败');
  },
  inspect(file) { return sendFile('inspect', file); },
  install(file) { return sendFile('import', file); },
  async start(packageId, version, saveName) {
    return requireOk(await fetch(`${BASE_URL}/${encodeURIComponent(packageId)}/${encodeURIComponent(version)}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ save_name: saveName }),
    }), '无法从世界包创建故事');
  },
  async uninstall(packageId, version, mode = 'safe', confirmed = false) {
    return requireOk(await fetch(`${BASE_URL}/${encodeURIComponent(packageId)}/${encodeURIComponent(version)}/uninstall`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, confirmed }),
    }), '卸载世界包失败');
  },
};
