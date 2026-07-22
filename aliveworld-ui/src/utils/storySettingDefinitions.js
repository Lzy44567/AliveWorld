export const STORY_SETTING_GROUPS = [
  {
    id: 'gameplay', title: '🎲 基础玩法', advanced: false, open: true,
    items: [
      ['showFutures', '显示未来可能性', '显示正文生成前参与物理抽取的近期未来候选。关闭只隐藏界面，不停止未来推演。'],
      ['showDice', '显示未来投掷结果', '显示本回合从有效未来候选中抽取到的结果。'],
      ['allowReroll', '允许重掷未来', '允许保留玩家行动并重新抽取另一个未来；会回溯本回合状态和偏好证据。'],
      ['aiSuggestions', '快捷行动按钮', '正文完成后提供 2–4 个可直接点击的下一步行动；关闭后不拼接相关提示词。'],
      ['entitiesEnabled', '启用暗流实体推演', '让活跃暗流实体在正文结束后异步行动；没有活跃实体时自动跳过。'],
    ]
  },
  {
    id: 'display', title: '👁️ 界面与实体显示', advanced: false, open: false,
    items: [
      ['showTime', '世界时间', '在界面顶部显示正文维护的当前世界时间。'],
      ['showEntityNames', '显示实体名称', '允许局内实体库显示实体名称；不影响实体是否参与推演。'],
      ['showEntityMotives', '显示实体动机', '允许显示实体动机，可能包含幕后信息。'],
      ['allowEntityEditing', '允许编辑实体', '开放局内实体编辑入口，主要用于创作和调试。'],
      ['showEntityBubbles', '显示实体气泡', '正文下方显示获准公开的实体变化提示。'],
    ]
  },
  {
    id: 'preferences', title: '🪞 用户偏好（高级）', advanced: true, open: false,
    description: '偏好影响内容倾向，不是强制清单。候选与行为证据不会直接控制正文。',
    items: [
      ['useUserPreferences', '启用用户偏好卡', '让正文参考已经生效且当前分类已开启的偏好；会要求保持多样性，不能机械重复满足。'],
      ['learnUserPreferences', '自动收集偏好证据', '复用正文结算记录中性的行为证据，不额外调用一次模型。'],
      ['deepPreferenceAnalysis', '自动深度分析偏好', '累积足够有效证据后，低频异步调用偏好分析模型并用 Python 更新后验。'],
      ['analyzeSensitivePreferences', '分析敏感内容偏好', '允许深度模型分析性、裸体等私密内容证据。默认关闭；开启后证据会发送给所配置的偏好模型。'],
      ['preferenceStoryEnabled', '剧情发展', '允许正文参考剧情节奏、走向、结局结构等偏好。'],
      ['preferenceAdultEnabled', '色情内容', '允许正文参考成人内容的题材、情境和表现重点偏好。'],
      ['preferenceActionEnabled', '动作描写', '允许正文参考战斗、动作强度、细节密度和反馈方式偏好。'],
      ['preferenceCharacterEnabled', '角色偏好', '允许正文参考人物类型、外观气质和角色表现偏好。'],
      ['preferenceRelationshipEnabled', '关系互动', '允许正文参考陪伴、冲突、羞耻、支配等关系体验偏好。'],
      ['preferenceVisualEnabled', '视觉与生图', '预留给生图和视觉工坊按需读取；当前正文只获得可用于叙事的部分。'],
    ]
  },
  {
    id: 'memory', title: '🧠 故事记忆（高级）', advanced: true, open: false,
    description: '达到上下文水位后异步归档较早完整回合；完整原文永久保留。',
    items: [['autoCompressMemory', '自动压缩故事记忆', '接近上下文预算时压缩较早回合，失败会继续使用完整原文，不影响正文。']]
  },
  {
    id: 'worldbook', title: '📚 世界书辅助（高级）', advanced: true, open: false,
    items: [
      ['worldbookCaptureEnabled', '捕获局内新设定', '正文明确建立长期世界规则时，异步判断并写入本局世界书；一次性事件不会捕获。'],
      ['worldbookCaptureReview', 'AI 内容二次确认', '所有 AI 捕获内容先标记为待确认，不直接成为启用条目。'],
    ]
  },
  {
    id: 'debug', title: '🧪 调试显示（高级）', advanced: true, open: false,
    items: [
      ['showInfluenceBubbles', '显示暗流影响气泡', '显示本回合实际触发并交给正文兑现的因果账单。'],
      ['showCausalLedger', '显示暗流因果账本', '开放当前故事完整因果账本入口，可能包含剧透。'],
    ]
  }
].map(group => ({
  ...group,
  items: group.items.map(([key, label, help]) => ({ key, label, help }))
}));
