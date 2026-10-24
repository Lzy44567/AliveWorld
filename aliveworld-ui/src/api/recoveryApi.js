const base = (kind, identity) => `/api/v1/generations/${kind}/${encodeURIComponent(identity)}/recovery`;
export async function listRecovery(kind, identity) {
  const response = await fetch(base(kind, identity));
  if (!response.ok) throw new Error('未能读取残稿，请重新载入核对；不要直接重复发送。');
  return (await response.json()).drafts;
}
export async function deleteRecovery(kind, identity, id) {
  const response = await fetch(`${base(kind, identity)}/${encodeURIComponent(id)}`, { method: 'DELETE' });
  if (!response.ok) throw new Error('删除残稿失败，原内容仍保留。');
}
