# M2：自动重要记忆与高光实施契约

日期：2026-10-05。Astra 设计，供 6.1 Sol 实施。基准源码 `7e1142a`，M1 `4a8051a`；本文件冻结下列有界 M2，不代表实现或真实模型质量验收。用户已授权设计后分阶段开发；不授权付费实测、版本提升、打包或远程发布。22l 的 M1 边界继续有效，冲突处仅以本文件明确替代项为准。

## 1. 玩家结果与范围

正常聊天的一次回复同时提议重要记忆；提交成功后，共同经历面板显示“自动重要”或“自动高光”、原因及原来源。玩家可取消自动选取、恢复、另行手动标重要或编辑纠正草稿。无逐条确认弹窗，无第二次分析调用。

范围仅当前会话中该 AI 对当前扮演者的认知。不是实际用户画像，不跨同卡会话共享，不分析历史全档，不新增 OOC 解析、背景调度、多气泡或容量回收。普通括号继续是原消息文本，不猜为场外权限；已能识别的非角色来源不得进入经历证据。

## 2. 严格协议与请求身份

注册独立 `character.reply.v2` 及对应提示词切片/契约目录。v1 的严格 `reply`、`ledger_ops` 两键和解析路径原样保留；v2 严格三键：`reply`、`ledger_ops`、`memory_annotations`。reply 和 ops 的原有限制、五种 kind、来源与引用规则全部不变。不得让 v1 接受新键，也不得宽松尝试 v2 失败后当 v1。

`memory_annotations` 为 0–6 项数组，每项严格为 `{op_index, reason}`：op_index 为非布尔整数，0 起，对应本次 ledger_ops 的唯一索引；同一 op 至多一项。reason 枚举如下。模型不能引用任意旧 entry_id 升级旧账本；需要纠正旧内容时正常 supersede 已投影目标，并给新 op 注解。无需重要变化时返回空数组，不强制每轮产出账本或高光。

新建会话默认初始化 memory v2 并采用 reply.v2；已有缺失/v1 memory 的会话继续 reply.v1，面板提供“启用自动重要记忆”显式操作，说明仅影响以后请求、不扫描历史，CAS/busy校验后原子升级。不是读时迁移，不要求玩家重建会话。请求开始时在 attempt 保存不可变 `reply_contract_id`，context、prompt、transport、stream preview、final parser、恢复核对使用同一个值。历史缺失值解释为 v1；未知值在调用前失败关闭。显式 retry/regenerate 是新 attempt，按当前会话设置选择版本，但旧 attempt 不改写。供应商不兼容时保留原正式回合并提示契约错误，不自动二次收费修复。

v1 会话仍可读取，原正式回合不批量迁移。只在新建或上述显式启用操作建立下述 memory v2 扩展；仅查看或M1手动标记不迁移。pending 冻结协议必须先持久化后调用，retry_input必须保留可追溯的原请求版本，重试的新attempt另记本次版本。提示词工作台中的旧 v1 覆盖不能默默套到 v2；新切片有独立身份与 manifest，覆盖不兼容时明确提示。`stream_json.ReplyPreview.feed`目前硬编码顶层key白名单，须显式接收版本并分别验证，不能只升级终态parser；fake provider依实际contract_id选择返回结构，不从正文场景猜协议。

## 3. 分类和证据（不是心理量表）

| reason | 程序派生等级 | 必需结构证据 |
| --- | --- | --- |
| explicit_preference | important | player_statement；关于当前 user；明确重要的喜欢、讨厌、情境限制，不是猜测 |
| explicit_boundary | important | player_statement；关于当前 user；明示边界、否认、拒绝或修正 |
| commitment | important | player_statement 或 dialogue_event；可归属的明确承诺，不以角色愿望冒充双方承诺 |
| relationship_turn | highlight | dialogue_event 的 experience，或关于 user 的 model_inference relationship |
| goal_turn | highlight | dialogue_event experience，或 model_inference intent/belief |
| conflict_repair | highlight | dialogue_event experience，或关于 user 的 model_inference relationship |

前两类要求 about_instance_id=user，且引用全部是玩家正式消息；显式重要程度由模型判断，代码只能校验身份与出处。后几类的主观判断在 UI 和上下文保留“角色理解/推测”来源，不升级世界事实、玩家同意或双方关系。AI 单方面说“我们和好了”不能作为玩家已确认的关系事实。拒绝、否认、厌恶不能反向推断相反欲望；强烈情绪、标点、露骨程度与重复生成不是独立高光证据。安静但重要的边界也可保护。

注解复用该 op 的原始 source、content、kind、visibility，不新增第二份自由文本事实或思维链。结构不合规整轮 CONTRACT_INVALID，不删坏注解后偷偷保存正文。合法来源不等于语义蕴含已被程序证明，玩家仍须可纠正。

## 4. 持久化与兼容

对被注解的新 ledger entry 添加可选严格对象 `memory_annotation: {version: 1, reason: <enum>}`。等级由代码从 reason 派生，不存重复文本、情绪分数或不同步 level。必须扩展持久记录验证器，对正式 ledger、inverse.previous_entries 和归档内容一致验证；未知注解版本失败关闭，不忽略。未带注解的旧项保持普通。

会话 `extensions.character_memory` v2 严格为 `{version: 2, important_entry_ids: [...], dismissed_auto_root_ids: [...], notice_ack_revision: 0}`。M1 的 8 个手动根语义不变；dismissed 最多 128 个规范 UUID、无重复；notice_ack_revision为非布尔非负整数且不大于会话revision。只存用户明确取消选取的根及通知确认水位；模型不能写。整体 extensions 仍受 32KiB 限制。v1 设置映射成空 dismissed/0水位的只读视图；首次显式启用原子升级，不做全盘迁移。旧 M1 二进制看到 version 2 已会拒绝相关读写；不能承诺比 M1 更早版本安全降级。

自动注解只作用该条当前 active 且来源有效的 entry，不因祖先高光就让所有后继自动继承高光。手动重要仍沿 M1 合法链继承；取消自动选取沿该合法 supersede 链的最早 entry 根继承，因此模型 supersede 不能偷偷重新启用。根查找检查同 session/subject/kind/about、可见性不扩大、有界遍历与循环。旧项重生成被替换后不成为另一轮独立证据。

用户取消/恢复接受 expected_revision、公开 active entry_id、显式 dismissed 布尔值；CAS/busy/权限前置，不用 toggle。不可借私有 ID 探测内容或链。取消仅移除自动等级的取材优先，不删除事实、不篡改原文、不取消独立手动重要；UI 分别显示两种状态。128 槽满时拒绝新取消并解释，可显式清理已失效取消项，不暗中重启活跃项。删除会话清除所有相关数据。

## 5. 容量、排序与去重

模型每轮仍最多 6 ops，active128、ledger2048、正式512、attempt4096、文件32MiB不变。自动等级不占用8个手动槽；也不保证常驻。每次 ledger 总32、intent8、统一 token 裁剪不变。

排序冻结为：有效手动保护→有效自动 important→有效自动 highlight→普通；同档依 M1 相关性、新近、ID。明确边界/喜好/承诺优先于戏剧性高光。先剔除已有效手动保护项，再从非手动项选最多16个自动优先名额（important先、highlight后）；兼具手动/自动的条目只按手动计一次、不占16名额。其余自动项参加普通相关性/新近排序，不删除注解或源记录；report仅实际获得自动优先的项标auto_important/auto_highlight。手动项仍先占32/intent8，遇intent上限跳过不挤掉可用非intent项；公开报告必须区分自动、玩家重要和预算省略，不能声称保护项永不被裁。

同请求重复 op_index 拒绝。相同当前来源集合、规范化引文集合、reason、subject/kind/about 的自动注解键若已有有效项，后来的同证据副本不新增自动优先及通知（原 ledger op 的合法性仍由既有契约判断）；合法 supersede 是内容修订而非新高光事件。不同来源不得仅凭相同文字合并；不声称这个确定性键能解决语义去重。重复模型转述不产生独立玩家证据。

非阻塞通知在正式提交后只提示当前公开新增自动选取汇总，最多一个可关闭提示，不抢焦点、不弹确认、不含私有数量。事件ID为session_id+action_id，事件水位为turn.committed_revision；有公开新选取且action.operation=send才产生事件。客户端显示后显式确认事件，服务端自行核对水位，以CAS原子单调更新notice_ack_revision；忙碌或丢响应先重载核对，再幂等补确认，不收费。确认不回滚故事，撤回也不降低水位。客户端另外持久保存本机已显示action_id的有界去重缓存，避免显示与ack之间崩溃重弹；缓存损坏安全降级成不弹而非补弹全历史。页面重载只显示面板现状，不补弹历史通知。重生成在现有实现中可能是新action，故不得只靠action_id去重：所有operation=regenerate只更新面板、不产生首次通知。取消/恢复与语义修订不伪造新的首次通知。通知中心的跨设备未读历史后置。

### 5.1 前后端共享API冻结

以下路由前缀均为`/api/v1/character-sessions/{sid}`，JSON请求严格只含列出键，全部必填，重复/未知键拒绝；revision非布尔非负整数，ID规范UUID。保持现有错误信封及CAS/busy先验。所有M2写响应统一`{session_id, revision, memory_settings}`，memory_settings只用下列public投影，不返回原extensions/整个session。

| 方法与路径 | 严格请求 | 语义 |
| --- | --- | --- |
| PUT /memory/automatic | expected_revision, enabled | enabled只能true；旧会话显式升级，v2重复启用幂等；不是允许无损降级的开关 |
| PUT /memory/automatic-selection | expected_revision, entry_id, dismissed | dismissed为布尔；公开active项取消/恢复其自动选择根，不动手动标记 |
| POST /memory/automatic-selection/release | expected_revision, root_entry_id | 仅释放已存在且确实不再有任何合法active后继的取消根；活跃私有后继不能伪称失效并释放 |
| PUT /memory/notice-ack | expected_revision, action_id | 不接受客户端revision水位；服务端只接受本会话真实公开send通知事件，按其committed_revision单调确认 |

现有PUT /memory/important和GET /memory/{entry_id}/sources保持路由/语义；important写不得将v2扩展重建成v1而丢字段。恢复选取通过当前公开entry设置dismissed=false；清理失效根独立入口，不接受批量任意ID清空。释放是否可行的投影只给玩家此前已取消过的根，不返回私有后继ID、文本或数量；无法安全说明时不列可释放。

v2 `memory_settings`严格公开字段：`version:2`、`automatic_enabled:true`、原M1的`important_entry_ids/protected_entries/inactive_root_ids`、`automatic_entries`、`inactive_dismissed_root_ids`、`notice_ack_revision`。automatic_entries只含当前公开、有效、带注解的项，每项`{entry_id, root_entry_id, reason, level, dismissed}`；level仅important/highlight；root只代表该公开项的合法修订链，不投影私有后继。inactive_dismissed_root_ids仅可安全释放的已知用户取消根。v1保留既有public_state形状，前端缺automatic_enabled视false，不强迫读时迁移。

生成成功响应可新增可选`memory_notice`，严格`{action_id, committed_revision, entry_ids}`，entry_ids只含本次首次公开自动选取、最多6个；无事件则字段缺失。生成流/查询最终action复用同一事件，不在accepted或preview提前通知。事件必须能由服务端正式turn、action.operation、added_entry_ids及校验后的公开注解重新核对；撤回/删除后的事件不再返回，旧ack可返回无变化已失效结果（同一上述写响应），不能确认任意更高水位。重生成一律无memory_notice。

取材report继续`{entries:[{entry_id, reason, state}]}`，reason白名单为`important`（兼容M1手动）、`auto_important`、`auto_highlight`、`related`、`recent`；state仍sent/budget/not_selected。自动优先16之外的项按related/recent说明本次排序，面板仍可显示其注解。不得返回模型评分、私有数量或未来消息计划。

## 6. 撤回、纠错、原子性

注解随新 entry 原子保存；reverse_ledger 删除新增项、恢复 previous_entries 时连同注解原样处理，不另造与 ledger_inverse 竞争的回滚链。模型提交失败、取消、迟到 attempt、保存失败不残留注解/通知。持久记录任何字段先验证完整候选，再同一次 replace 提交。重启中断沿现有 pending 恢复，不自动调用模型。

用户取消选取是独立设置，不应因撤回故事回合恢复成允许：失效根保留且无效，可显式清理；撤回 supersede 后原 active 项恢复，取消状态仍按根派生。手动标记同 M1。撤回新 entry 时不能留下可召回的虚假高光；重生成先在副本撤旧回合，不能用被替换消息作证据。

纠正内容复用可编辑草稿；不得覆盖现有草稿或自动发送。新消息是真实来源，合法 supersede 后才显示记录已更新。模型未做 supersede 时只能说“纠正消息已发送”，不能承诺修好。允许取消错误的自动选取，不能把取消解释为玩家承认相反事实。

## 7. 职责与实施片

- 独立 memory/annotation 纯函数：类型/版本、分类结构校验、合法链、去重、排序与安全投影。
- contract：显式协议分派、op索引映射、entry注解，继续单一 ledger 事务。
- context/prompt registry：按冻结契约拼装及最终预算；M2不扩大 allowed_messages。
- service/repository：pending身份、CAS、失败恢复、设置写入与原子提交；API只校验映射白名单。
- frontend api/store/panel：取消/恢复、等级/来源、非阻塞汇总、迟到会话隔离。不要全部塞在service或面板组件。

实施可分 M2a协议/领域和合成窄测，M2b事务/API/兼容回归，M2c可见玩家闭环及浏览器验收。只完成a不宣称M2交付。禁止读取真实私聊夹具、付费评测或批量迁移玩家数据。

## 8. 验收与停止门

实施状态（2026-10-05）：M2a/b/c源码闭环已完成；完整Python571、Node99、可见性、153模块构建与完整Edge36（5.2m）通过，专项及宽窄截图已验，详细证据见TESTING。无真实模型语义验收、版本/包/远程动作。下一门22p容量诊断是独立设计，不代表扩容已完成；C3/C4/C5未实现。

至少覆盖：v1严格回归与v2未知/重复字段、索引越界/布尔、未知版本；请求冻结与恢复，v1旧存档读不写；6项/128/2048/32KiB/32与8/16边界；公开与私有全路径；不存在/撤回/归档/跨会话来源；安静边界/承诺/关系误解/情绪修辞/否认拒绝合成案例；相同来源去重、重生成不重复通知；supersede恢复/取消继承/手动优先独立；取消/恢复CAS/busy/丢响应/保存故障/迟到提交；预算裁剪后报告与真实请求相同。

真UI闭环：聊出公开自动项→看到原因及来源→取消→重载保持→恢复→独立手动标重要→纠正草稿保留用户输入→发送后只呈现实际修订→撤回/重生成→无假高光或重弹通知。宽窄视觉、键盘、流式/非流式、会话切换回归。

完成窄测后跑项目 Python/Node/可见性/生产构建/完整 Edge；更新 ACTIVE、路线、CHANGELOG、TESTING 的实际证据。未付费跑真实模型须直说自然度未验。M2满足上述闭环且无P0/P1则停止本片，转22n容量门；不自行宣布长期无限记忆或把未冻结后续写进代码。
