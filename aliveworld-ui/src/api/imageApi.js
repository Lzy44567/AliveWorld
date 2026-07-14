const API_ROOT = 'http://127.0.0.1:8000';
const API_URL = `${API_ROOT}/api/v1/game`;

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 405) throw new Error('后台仍是旧版本，尚未载入这个生图接口。请关闭 AliveWorld 的前后端窗口并重新运行 start_dev.bat。');
    throw new Error(data.detail || '生图请求失败');
  }
  return data;
}

function jsonOptions(payload, method = 'POST') {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) };
}

export const imageApi = {
  apiRoot: API_ROOT,
  listTasks(sessionId) {
    return request(`${API_URL}/${sessionId}/images/tasks`);
  },
  listLibrary() {
    return request(`${API_URL}/images/library`);
  },
  getLibraryTask(scopeId, taskId) {
    return request(`${API_URL}/images/library/${encodeURIComponent(scopeId)}/tasks/${taskId}`);
  },
  deleteLibraryTask(scopeId, taskId) {
    return request(`${API_URL}/images/library/${encodeURIComponent(scopeId)}/tasks/${taskId}`, { method: 'DELETE' });
  },
  regenerateLibraryTask(scopeId, taskId) {
    return request(`${API_URL}/images/library/${encodeURIComponent(scopeId)}/tasks/${taskId}/regenerate`, { method: 'POST' });
  },
  createTask(sessionId, data) {
    return request(`${API_URL}/${sessionId}/images/tasks`, jsonOptions({ data }));
  },
  compileAndCreateTask(sessionId, task, compile) {
    return request(`${API_URL}/${sessionId}/images/tasks/compile-and-start`, jsonOptions({ task, compile }));
  },
  compilePrompt(sessionId, payload) {
    return request(`${API_URL}/${sessionId}/images/prompts/compile`, jsonOptions(payload));
  },
  cancelTask(sessionId, taskId) {
    return request(`${API_URL}/${sessionId}/images/tasks/${taskId}/cancel`, { method: 'POST' });
  },
  retryTask(sessionId, taskId) {
    return request(`${API_URL}/${sessionId}/images/tasks/${taskId}/retry`, { method: 'POST' });
  },
  regenerateTask(sessionId, taskId) {
    return request(`${API_URL}/${sessionId}/images/tasks/${taskId}/regenerate`, { method: 'POST' });
  },
  deleteTask(sessionId, taskId) {
    return request(`${API_URL}/${sessionId}/images/tasks/${taskId}`, { method: 'DELETE' });
  },
  setPortrait(sessionId, taskId, characterName, imageIndex = 0, scope = 'local') {
    return request(`${API_URL}/${sessionId}/images/tasks/${taskId}/set-portrait`, jsonOptions({ character_name: characterName, image_index: imageIndex, scope }));
  },
  checkComfyUI(baseUrl) {
    return request(`${API_URL}/images/providers/comfyui/check`, jsonOptions({ base_url: baseUrl }));
  },
  listWorkflows() {
    return request(`${API_URL}/images/workflows`);
  },
  importWorkflow(data) {
    return request(`${API_URL}/images/workflows`, jsonOptions({ data }));
  },
  listReferences(sessionId) {
    return request(`${API_URL}/${sessionId}/images/references`);
  },
  uploadReference(sessionId, payload) {
    return request(`${API_URL}/${sessionId}/images/references`, jsonOptions(payload));
  },
  deleteReference(sessionId, referenceId) {
    return request(`${API_URL}/${sessionId}/images/references/${referenceId}`, { method: 'DELETE' });
  },
  testComfyUI({ baseUrl, checkpoint, workflowId }) {
    const query = new URLSearchParams({ checkpoint, workflow_id: workflowId });
    return request(`${API_URL}/images/library/test?${query}`, jsonOptions({ base_url: baseUrl }));
  },
  absoluteImageUrl(path) {
    return path?.startsWith('http') ? path : `${API_ROOT}${path || ''}`;
  }
};

export function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error(`无法读取文件：${file.name}`));
    reader.readAsDataURL(file);
  });
}
