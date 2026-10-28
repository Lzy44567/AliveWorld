const base = session => `/api/v1/game/${encodeURIComponent(session)}/attempts`;
async function request(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || '旧尝试操作失败');
  return data;
}
export const listStoryAttempts = session => request(base(session));
export const deleteStoryAttempt = (session, id) => request(`${base(session)}/${encodeURIComponent(id)}`, { method: 'DELETE' });
