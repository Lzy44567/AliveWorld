async function readPayload(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `反馈操作失败（HTTP ${response.status}）`);
  return payload;
}

export const feedbackApi = {
  async context() {
    return readPayload(await fetch('/api/v1/feedback/context', { cache: 'no-store' }));
  },
  async preview(payload) {
    return readPayload(await fetch('/api/v1/feedback/preview', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    }));
  },
  async exportPackage(payload) {
    const response = await fetch('/api/v1/feedback/export', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `导出失败（HTTP ${response.status}）`);
    }
    const disposition = response.headers.get('content-disposition') || '';
    const match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    return { blob: await response.blob(), filename: match ? decodeURIComponent(match[1]) : 'AliveWorld-diagnostic.zip' };
  },
};
