const ERROR_DETAILS = {
  prompt_content_rejected: {
    stage: '提示词整理阶段',
    message: '提示词模型服务商拒绝了本次内容。正文与 ComfyUI 尚未执行；可改用允许该内容的合规模型，或手写生图提示词后选择“直接使用当前提示词”。',
  },
  prompt_connection_error: {
    stage: '提示词整理阶段',
    message: '无法连接用于整理生图提示词的大语言模型，请检查模型 API、网络与代理设置。',
  },
  prompt_empty_response: {
    stage: '提示词整理阶段',
    message: '提示词模型返回了空内容，ComfyUI 尚未执行。可重试或改用直接提示词。',
  },
  prompt_format_error: {
    stage: '提示词整理阶段',
    message: '提示词模型没有返回可解析的格式，ComfyUI 尚未执行。可重试或改用直接提示词。',
  },
  prompt_compilation_error: {
    stage: '提示词整理阶段',
    message: 'AI 整理生图提示词失败，ComfyUI 尚未执行。',
  },
  provider_submit_error: {
    stage: 'ComfyUI 提交阶段',
    message: '提示词已经整理，但任务未能提交给 ComfyUI。请检查地址、工作流、模型选择和 ComfyUI 状态。',
  },
  provider_execution_error: {
    stage: 'ComfyUI 生成阶段',
    message: '任务已进入 ComfyUI，但执行或读取结果失败。请查看 ComfyUI 队列和控制台。',
  },
  provider_error: {
    stage: 'ComfyUI 阶段',
    message: '提示词已经整理，但 ComfyUI 生成失败。',
  },
};

export function imageFailureDetail(task = {}) {
  const detail = ERROR_DETAILS[task.error_code] || {
    stage: '生图任务',
    message: '任务失败，暂时无法确定具体阶段。',
  };
  const raw = String(task.error_message || '').trim();
  return {
    ...detail,
    full: `${detail.stage}失败：${detail.message}${raw ? ` 技术信息：${raw}` : ''}`,
  };
}
