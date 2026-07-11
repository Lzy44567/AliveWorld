# 暗流因果账本：v1.2 实现边界

完整设计以工作空间根目录保留资料中的同名文档为准。本项目切片实现：

- 中心账本保存完整潜在影响，实体 YAML 保存同 ID 的 `influence_refs` 索引。
- 类型：`one_shot / persistent / evolving`。
- 条件触发，无概率；变数 AI 判断条件，Python 校验 ID，所有满足项交给正文兑现。
- Python 维护 `age_ticks / attempt_count / trigger_count` 和消费策略。
- 来源死亡动作：`remove / release / keep`；生命关联强度是可编辑语义值，不作为硬阈值。
- 世界时间只保存文本，不计算。
- 当前故事可在实体库的调试二级页查看和编辑完整账本；默认隐藏。
- 概率、寿命和威力衰减、世界时间推算均不在本切片。
