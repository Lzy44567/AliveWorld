export async function worldbookCollaboration(sessionId, change) {
  const response = await fetch(`/api/v1/game/${encodeURIComponent(sessionId)}/worldbook-collaboration`, change ? {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(change),
  } : undefined);
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || '世界书协作操作失败');
  return data;
}
