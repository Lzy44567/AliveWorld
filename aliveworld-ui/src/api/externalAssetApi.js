const BASE_URL = '/api/v1/external-assets';

async function send(path, file, kind, name = '') {
  const query = new URLSearchParams({ filename: file.name, kind });
  if (name) query.set('name', name);
  const response = await fetch(`${BASE_URL}/${path}?${query}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/octet-stream' },
    body: file,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || '外部资产处理失败');
  return data;
}

export const externalAssetApi = {
  inspect(file, kind) { return send('inspect', file, kind); },
  import(file, kind, name) { return send('import', file, kind, name); },
};
