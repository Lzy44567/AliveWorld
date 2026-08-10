async function readPayload(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `检查失败（HTTP ${response.status}）`);
  return payload;
}

export const updateApi = {
  async check(includePrerelease = true) {
    const response = await fetch(
      `/api/v1/updates/check?include_prerelease=${includePrerelease ? 'true' : 'false'}`,
      { cache: 'no-store' },
    );
    return readPayload(response);
  },
  async prepare(includePrerelease = true) {
    return readPayload(await fetch(
      `/api/v1/updates/prepare?include_prerelease=${includePrerelease ? 'true' : 'false'}`,
      { method: 'POST' },
    ));
  },
  async status() {
    return readPayload(await fetch('/api/v1/updates/status', { cache: 'no-store' }));
  },
  async cancel() {
    return readPayload(await fetch('/api/v1/updates/cancel', { method: 'POST' }));
  },
  async install() {
    return readPayload(await fetch('/api/v1/updates/install', { method: 'POST' }));
  },
};
