export async function stopGeneration(kind, identity, requestId) {
  const response = await fetch(`/api/v1/generations/${kind}/${encodeURIComponent(identity)}/${encodeURIComponent(requestId)}/stop`, { method: 'POST' });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || '停止请求失败');
  return data;
}
