"""Safe, local error descriptions shared by HTTP and SSE; no upstream text."""
ERROR_STATUS = {'INVALID_REQUEST': 400, 'ROLE_FIELDS_INVALID': 422, 'SESSION_NOT_FOUND': 404, 'ACTION_NOT_FOUND': 404,
    'SESSION_DELETED': 410, 'REVISION_CONFLICT': 409, 'SESSION_BUSY': 409, 'IDEMPOTENCY_MISMATCH': 409,
    'STALE_RETRY': 409, 'SCHEMA_READ_ONLY': 409, 'PROFILE_FROZEN': 409, 'MEMORY_VERSION_UNSUPPORTED': 409,
    'SESSION_LIMIT': 413, 'INPUT_LIMIT': 413, 'CONTRACT_INVALID': 422, 'CONTEXT_LIMIT': 422, 'MEMORY_MARK_LIMIT': 409,
    'CONNECTION_UNSUPPORTED': 422, 'CAPACITY_LIMIT': 429, 'PROVIDER_RATE_LIMIT': 429,
    'PROVIDER_TIMEOUT': 504, 'PROVIDER_FAILED': 502, 'PROVIDER_TRUNCATED': 502, 'STREAM_UNSUPPORTED': 502}
ERROR_MESSAGES = {'SESSION_BUSY': '当前对话正在生成，请等待或停止。', 'REVISION_CONFLICT': '对话已更新，请刷新后再操作。',
    'ROLE_FIELDS_INVALID': '角色独立字段格式或长度不受支持，请修订原文件后重新导入，或转为自由文本编辑。',
    'CONNECTION_UNSUPPORTED': '请先在设置中配置可用的角色文本模型接口。',
    'CONTEXT_LIMIT': '必要角色资料与近期对话超出上下文预算，请缩小资料或调整接口预算。',
    'PERSISTENCE_FAILED': '保存失败，对话已暂停写入，请重启后核对状态。',
    'SESSION_DELETED': '此对话已删除，请用新的创建标识开始新对话。',
    'SESSION_LIMIT': '此对话已达到记录或文件上限，原内容仍可查看，请新建对话继续。',
    'MEMORY_MARK_LIMIT': '最多标记8条重要记忆，请先取消一条（失效标记也可取消）。',
    'MEMORY_VERSION_UNSUPPORTED': '此会话的记忆格式来自其他版本，请升级后再操作；原文件未修改。',
    'INPUT_LIMIT': '输入或角色资料超过保护上限，请缩小相关字段后再试。',
    'CONTRACT_INVALID': '模型返回的JSON或来源记录不符合契约，本轮未保存，原历史保留。',
    'PROVIDER_FAILED': '模型连接或服务异常，本轮未保存，请检查或测试接口后显式重试。',
    'PROVIDER_TRUNCATED': '模型输出未完整结束，本轮未保存，可调整输出预算后显式重试。',
    'PROVIDER_TIMEOUT': '模型响应超时，本轮未保存，请稍后显式重试。',
    'PROVIDER_RATE_LIMIT': '模型服务限制了请求频率，请稍后显式重试。',
    'CAPACITY_LIMIT': '角色请求已达并行上限，请等待其他请求完成后再试。',
    'SCHEMA_READ_ONLY': '此对话来自更高版本，仅可安全查看，请使用升级后的应用。',
    'STREAM_UNSUPPORTED': '本接口流式请求失败，可显式选择非流式后重试。'}


def message(code):
    return ERROR_MESSAGES.get(code, '请求无法安全完成，请核对对话状态。')


def retryable(code):
    return code in {'PROVIDER_FAILED', 'PROVIDER_TIMEOUT', 'PROVIDER_RATE_LIMIT', 'STREAM_UNSUPPORTED', 'CONTRACT_INVALID', 'PROVIDER_TRUNCATED'}
