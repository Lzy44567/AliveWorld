export async function fetchWorldbookActivity(sessionId, { offset = 0, details = false } = {}) {
  const res = await fetch(`/api/v1/game/${encodeURIComponent(sessionId)}/worldbook-activity?offset=${offset}&details=${details}`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '读取修订记录失败');
  return data;
}
