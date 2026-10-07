# C4-B 消息组存储、事务与合成迁移合同

2026-10-06，Astra实施设计；承接22u，不重新讨论已确认玩法。仅设计，不执行真实数据迁移。存储schema新版本取2，与输出character.reply.v3是两个独立版本；memory扩展version仍保持原值。无数据库、事件总线、插件或分段存储扩建。

## 2026-10-07 隔离实现与工程细化（当前生效）

2026-10-08 B5a准备片：主代理全文读取第13节后，提取`context._build_context`供真实消息批共享旧协议装配/预算，新增`legacy_context.py`；旧schema1入口仍供应实际双消息，兼容入口供应schema2真实多消息组，不造假turn。V1/V2×LEGACY/M3/C3、默认/冲突/OOC、旧regenerate源排除及整组预算有7项测试；显式schema2逻辑组capacity另有3项。第13节的legacy_execution字段验证、重试/提交纯生命周期、服务分派尚未实施；本片不能执行旧retry，生产入口及玩家数据不变。

B4独立`group_service.py`已将真实async worker接到隔离schema2 repository；不由前端订阅或页面生命周期拥有任务。生成槽在领取前预留，生成完成立即释放，gaps由服务器短计时事务送达；正常批末合并已排队输入，失败/取消停住，不自动收费。启动恢复worker仅送有效候选尾，旧队列留待显式继续；恢复期间新输入是新的明确授权。取消后立即retry/send通过待唤醒记录避免旧worker finally丢失新任务。事件只带单组正式前缀及轻量游标/计数，不反复包含全部历史或私人账本；GET当前历史最多20组及未回应输入。生产路由/创建默认不变，旧attempt执行适配仍未实现。本片无玩家文件读写或新包。

B3上下文片已接到隔离组事务：`group_context.py`按attempt截止与领取身份构建`current_user_messages/current_ooc_notes`，不合成旧turn。共享memory/recall/world reader显式支持schema2，旧schema1路径保留；独立C4四切片不沿用旧覆盖。正式历史按最近20个完整结束组、seq排序，当前输入单独发送；超额队列未领取输入即便早于截止也排除。候选尾、撤回/替换组、历史OOC不作来源。重生成先逆账；旧原文召回保持ID/seq，预算整组裁剪与最终证据闭包。本片仍未接生产服务/UI或真实迁移；下一是后台调度与旧attempt适配，不是打包完成。

已完成B1纯转换/reader/严格校验及B2纯事务原型：旧repository默认仍schema1，仅隔离测试显式注入schema2 validator；没有生产路由/默认格式切换，没有真实文件转换。共享账本planner供旧双消息和新组使用；不把多输入合成假消息。

- `character.context.c4.v1`承载未来独立输入数组；schema1明确拒绝C4/v3，不把支持新协议等同已有存档可用。
- 旧attempt加显式`legacy_attempt=true`、旧临时输入保存为`legacy_retry_snapshot`；旧重生成的输入ID原本是新ID，保留其原regenerate owner，并仅对明确legacy记录允许这种输入所属关系。不能按正文相同合并身份。
- undo无模型请求，其幂等attempt明确`control_attempt=true`，只有undo/committed及基础控制字段，不伪造v3输出attempt。
- `ledger_plan`每项仅`entry`和可选`previous_entry`；校验候选来源、可见性、注解、原目标、反向身份与容量。候选不进入正式来源；本组尾部可作预验证依赖，批末才结算。
- 自动认领在最近失败/取消/中断后停止；显式继续/重试才可重启。失败原输入+后续排队可能超过一次请求上限，按原顺序有界前缀认领（≤8条、正文≤4000、OOC≤1000），其余不丢失，下批处理，不永久卡死或放大预算。
- failed/cancelled/interrupted档案不占512个正式组容量，仍受4096 attempts/2048 actions/文件限额。合法重生成重试与初次重生成一样预扣被替换组。
- 批操作依赖屏障以本批认领输入截止为准，不按最后AI气泡序号：A→玩家X→B之后不能撤回/替换X所依赖的旧批。失败档案可引用后来已withdrawn的输入，避免成功重试撤回时自相矛盾。
- UTC候选到期时间与新消息时间严格验证；恢复重新安排剩余短间隔，timer通过group+ordinal幂等。旧已读ACK不回退游标，不将候选当未读。

29项隔离测试覆盖以上状态及旧多次重生成/撤回/场外/来源身份、磁盘失败。下一仍是C4上下文/服务调度/旧协议重试适配、前端数组气泡与原位确认、全量浏览器及迁移门；不能将纯函数测试称为完整后台自动送达或可打包C4。

## 1. 当前实现与最小改动边界

repository.py已经提供单会话mutation_guard、深拷贝、validate_session、临时文件/fsync/os.replace；继续使用一个会话JSON作为事务聚合，不增加跨文件提交。models当前schema_version=1，turns是双消息回合；service.archive_last将整轮挂在原action并reverse_ledger；memory.formal_messages及context.build_context直接遍历双消息，需要统一适配，不能仅改API数组。

硬限额保持MAX_TURNS=512、MAX_ACTIONS=2048、MAX_ATTEMPTS=4096、MAX_LEDGER=2048、MAX_ACTIVE=128、文件32MiB、快照8MiB、extensions32KiB。组最多6气泡/总8000字符，单个输入≤4000；待回应集合≤8条且合计≤4000，OOC合计沿既有C3上限。UI“还能发送”不构成容量承诺，保存前验证权威状态。

以下字段为B片冻结工程结构，函数名可按既有风格微调；不得同时维护一套可写turns和一套可写groups造成双权威。

## 2. schema2根字段

| 字段 | 类型/约束 |
| --- | --- |
| schema_version | 固定2；删除墓碑仍仅schema_version/session_id/deleted |
| session_id/creation_fingerprint/participants/world_binding/opening/created_at | 沿用原身份及冻结快照，迁移不重建ID或人设 |
| title/presentation_mode/revision/updated_at/extensions | 沿用原验证；revision是外部CAS，extensions不塞队列正文 |
| context_epoch | 非负整数；上下文破坏性变化递增，普通追加输入不变 |
| next_seq | 下一个正式通信序号，正整数且大于所有已分配seq；不回退复用 |
| read_ai_seq | 非负单调已读游标；0初始，不能超出已分配正式AI最大seq |
| inputs | 正式玩家输入记录数组，含已归档记录；消息正文唯一存储处 |
| groups | 有正式/候选/归档身份的组记录数组；按创建顺序存，不靠数组位置推测状态 |
| requests | 操作幂等记录/attempt，见第5节 |
| ledger | 沿用现有entry结构，created_turn_id指向group_id，字段不批量改名 |

schema2不存turns。API旧turn投影只能适配旧schema，不能把新多输入组伪造成单user_message。读取未知更高版本保留只读，所有写路径拒绝。

## 3. 正式输入与气泡字段

inputs每项严格为input_id、action_id、message、ooc_note?、status。input_id等于message.message_id；action_id关联接受该输入的send操作；status=active|withdrawn。输入在服务端接受时即正式持久，不等模型成功。已失败生成不撤销玩家输入。

message沿用message_id/speaker_instance_id/content/presentation_mode/visibility/created_at，新增seq。旧turn_id若存在仅为兼容来源出处，保留不改，不再用于判定成员关系；新消息不需要turn_id，组成员以input_ids及气泡容器为准。OOC位于输入记录而非message.content，不能作证据。所有消息seq在会话内唯一，ID在正式/候选/归档全集不冲突。

候选气泡项严格ordinal、message。ordinal=0..N-1；message在候选时没有seq/created_at，以候选组generated_at记录生成时间；正式送达事务才写seq和created_at。迁移旧消息直接保留原created_at。正式送达前缀长度以group.delivered_count唯一判定，候选不加一个容易漂移的delivered布尔。

归档消息仍保留seq和原文用于审计，但不算当前正式来源；next_seq永不因撤回回退。read_ai_seq可指向已归档的旧seq，未读按当前active正式AI且seq>游标过滤，不因撤回倒退游标重报旧消息。

## 4. 组字段表

| 字段 | 约束/语义 |
| --- | --- |
| group_id/action_id/request_id | 稳定UUID；旧group_id保留旧turn_id；所属attempt唯一 |
| input_ids | 1–8个有序active输入ID，原认领集合，不重复；重生成可复用集合 |
| mode_at_generation/display_mode | messenger/roleplay；stream/gaps/instant，attempt快照 |
| status | generating、delivering、complete、failed、cancelled、interrupted、replaced、withdrawn、partial_failed |
| created_at/generated_at?/settled_at? | UTC；生成完成才有generated_at，终态有settled_at |
| bubbles | 有界气泡数组；generating时空，验证前不保存流式正文 |
| delivered_count | 0..len(bubbles)，正式连续前缀；complete必须等于长度 |
| next_due_at | delivering且有余量时UTC，否则null；恢复重排 |
| ledger_plan | 验证后归一化op/注解及稳定entry ID，结算后清空；不是当前ledger |
| ledger_inverse | 现有added_entry_ids/previous_entries形状，未结算为空 |
| memory_notice? | 沿用现有notice形状及来源约束，结算才生成 |
| committed_revision? | complete/partial_failed时最终结算revision；每条消息的seq不是revision |
| replaced_by_group_id? / error_code? | 仅相应终态出现，错误码不得含正文 |

完整候选验证成功才填bubbles/ledger_plan；stream/instant可直接由generating原子到complete，不强制落一个中间候选文件。gaps首条与候选保存同事务进入delivering。失败但没正式AI时bubbles保持空或清除未正式候选；不保存坏JSON预览。

ledger_plan只能由代码构建，含已映射来源和程序分配entry ID，不接受模型自报。现有预算报告等诊断不重复持久大段上下文。候选正文随组存在但公共投影严格只暴露正式前缀。

## 5. 操作、attempt与输入认领

request保留action_id、operation(send|regenerate|undo)、fingerprint、created_at、mode_at_action、result_state；新增input_id?(send)、target_group_id?(批操作)、result_group_id?、resolved_by_group_id?、attempts。fingerprint覆盖原payload语义，不把服务器分配seq混入。排队send允许attempts为空，这是schema2明确变化，不向旧validator偷渡。

认领时选择最早未解决send action为owner，在它下面创建attempt；其余输入action在成功结算时resolved_by_group_id指向同组，不各造一次请求。queued状态由输入active、无active认领且未resolved派生，不维护第二份可漂移队列数组。

attempt字段：request_id、base_revision、context_epoch、history_cutoff_seq、input_ids、group_id、reserved_ai_ids(6个)、reply_contract_id、context_contract_id、display_mode、status、created_at；可选ended_at/error_code/committed_revision/retry_of/retry_token。status沿pending/committed/failed/cancelled/interrupted；候选持久成功后attempt=committed（生成已成功），组仍可delivering，忙碌判断必须同时看组，不能只看pending_attempt。

失败/取消/中断后原input_ids仍active。显式retry使用同输入集合和原协议快照新attempt，不重复输入；下一次普通发送可将未解决旧输入和新增输入一起认领，此时旧失败action不得再重试造成双回应。生成快照原文从不可变inputs读取，不重复保存retry_input正文。

失败后暂不自动认领后续队列：派生“待玩家继续”状态。普通新发送/显式重试是继续意图；正常成功批结束自动认领后续输入，不轮询模型。一个会话只允许一个generating/delivering组，供应商并发仍受既有4槽控制；无槽时输入可保存排队，不能宣布已发请求。

## 6. 统一reader与适配职责

- validate_session分派validate_schema1/validate_schema2；repository load/create/transaction/delete的版本判断集中SUPPORTED_SCHEMAS，不能散落“!=1”。schema1写保留旧流程直到迁移获准，schema2才用新组流程。
- formal_messages(session)：schema1旧逻辑；schema2返回active inputs及未replaced/withdrawn组的已送达前缀，永远排除候选、坏预览和归档AI。失败输入依然正式但不自动成为已回应事实。
- active_group_ids/order：替换memory.valid_candidates/select_memory对turns的直接依赖；created_turn_id仍映射合法active组；未结算组无新ledger。
- conversation_projection：返回按seq的正式消息及组关联，用于UI/列表/来源详情；opening独立保留，不能赋予玩家来源身份。
- context.build_context_v3：近期最多20个已结算组+本次input_ids；各组输入只取一次，按正式seq呈现，当前认领输入从history排除以免重复；其他未认领输入不泄露进本次快照。
- 当前输入通过current_user_messages数组及与message_id绑定的current_ooc_notes投影，新增明确context协议身份，不给C3原单字段偷偷改数组。继承M3召回/C3边界，旧attempt继续旧context协议。
- 预算裁剪以完整组/完整原文为单位，继续保留至少既有最小近期量规则；连发总4000是请求上限，不是把每条扩到4000。world/recall检索可用确定性连接文本取关键词，但证据仍独立ID/逐字引文。
- capacity_report(schema2)：报告active逻辑组数、操作和attempt，候选组也预留位置；不泄露私人ledger数。未知schema拒绝检查。

## 7. 沿用ledger校验而不假造turn

将contract._plan_turn中的op验证抽成共享纯函数：输入正式allowed_messages、本次输入集合、本组候选ID映射、projected_entry_ids、AI/user身份，输出规范化plan及容量模拟结果。旧plan_turn调用同函数保持回归；新plan_group不制造合并reply或虚拟玩家消息绕旧校验。

保留source种类、逐字引文、visibility、about、annotation、supersede同kind/同about/active及来源封闭规则。仅dialogue_event的“当前消息集合”从二元组扩为认领输入+本组AI；历史召回仍不可重包装为当前经历。M2 notice只在最终结算生成。

stream/instant消息+全部op+inverse同事务；gaps最后一条+全部op+inverse同事务。逐条送达前不修改ledger。账本写/偏好/模式等语境操作在忙时拒绝，因此候选旧entry不会合法并发变更。保存失败保留权威原状；发布事件必须在repository返回成功后。

## 8. 操作冲突矩阵

| 操作 | idle | generating | delivering | revision/epoch |
| --- | --- | --- | --- | --- |
| 接受正式输入 | 保存并认领 | 保存排队 | 保存排队 | revision+1，epoch不变 |
| 已读ack | 可 | 可 | 可 | revision+1仅游标确有前进，epoch不变 |
| 标题修改 | 可 | 可 | 可 | revision+1，epoch不变 |
| display设置 | 下次attempt快照 | 只影响下一次 | 只影响下一次 | 若存服务端revision+1，epoch不变 |
| 模式/偏好/记忆修改 | 可，须无待回应输入 | SESSION_BUSY | SESSION_BUSY | revision+1，epoch+1 |
| 批撤回/重生成 | 最新且无后续输入依赖 | SESSION_BUSY | SESSION_BUSY | 见下节，epoch+1 |
| 既有停止生成 | 无pending则幂等无改变 | 取消pending | 不扩为停止气泡，返回当前状态 | 成功取消revision+1、epoch+1 |
| 定时送达 | 不适用 | 不适用 | 验group/next_index/due幂等提交 | revision+1，epoch不变 |
| 删除会话 | 无忙且CAS符合 | SESSION_BUSY | SESSION_BUSY | 写schema2墓碑 |

pending完成提交检查request仍pending、epoch等于快照、input_ids仍active且本组独占认领、历史截止前内容未替代、ledger计划仍有效；普通追加输入使revision变化不构成失败。严禁简单取消base_revision保护而无替代检查。外部CAS仍严格；冲突客户端刷新后用同action_id重投，不能重复输入。

## 9. 批撤回、重生成与恢复

撤回保持旧“整轮撤回”语义：撤回最新完成组及其认领输入（inputs标withdrawn，不物理删除）；逆转实际inverse，组status=withdrawn，所有相关action标withdrawn。任何后来正式输入即使尚未被回应也阻止撤回，避免误删上下文。原文保留审计、不入formal_messages。

重生成复用原input_ids，旧组在新生成成功前保持正式。新请求上下文排除旧组AI并模拟逆账；提交时旧组replaced、逆旧账、新组首发/账本按模式处理原子发生。gaps从首条替换开始旧组不再当前来源，新组余量继续；失败发生在候选验证前不替换旧组。若生成期间收到新玩家输入，替换提交拒绝，保留旧组和新输入，失败新候选不送达，不能把回应旧内容的玩家话移到新剧情。

archive_last替换为archive_group：状态和inverse处理在同一JSON内，不在requests再复制整组正文；旧action查询通过result_group_id读档。历史归档不能被召回，不改变旧message_id；待发候选不能伪装正式归档。

启动恢复仅服务启动执行：pending→interrupted并禁止自动重试；delivering候选重校验后重设下一短间隔；已正式气泡不重播。损坏/未知版本不修改。瞬时磁盘失败留候选等待恢复，不自动部分终止；确需partial_failed时仅应用依赖全正式的op子集并原子结算。恢复与GET不能竞争改状态。

## 10. 容量与不扩容计数

active组（含generating/delivering）最多512；所有groups包括归档受现有requests/attempts≤2048/4096及文件32MiB共同约束，不能无限归档。inputs总量不得超过send action数≤2048；多气泡最多6×现存组且仍受文件硬限。每新输入消耗一个action，不给连发免费无限额度。

认领前预留一个组位、一个attempt和供应商槽；接受排队输入前保证至少还有未来组位及队列容量，满则拒绝且客户端草稿不丢。候选保存前检查整体规范化文件大小及最坏提交体积（seq/time/inverse/ledger），不足首发前失败；不能依赖实际最后os.replace才发现容量不够。inverse字段上限继续每组6，不扩ledger总量。

## 11. 合成迁移算法（真实会话不运行）

1. schema1严格验证后深拷贝，保留根冻结字段/ledger/extensions/opening/revision；转换函数纯内存，不调用repository.write。schema2输入校验后原样返回，未知版本拒绝。
2. 按旧requests顺序枚举active turns及各action.archived_turn建立组。group_id=旧turn_id、input_id=旧user_message ID、AI ID/inverse/source/created_at完全保留。归档组根据旧result_state映射withdrawn/replaced；active组complete；每组一个AI气泡且delivered_count=1。
3. 同一input message ID仅存一份；若重生成旧结构不同分支原本使用不同user ID，保留不同ID而不猜合并，只有active分支输入为active，归档独占输入withdrawn。内容相同不是合并依据。同ID不同正文拒绝迁移。
4. 为旧消息分配确定性seq：先按原turns顺序枚举所有active组，组内user在AI前；再按requests顺序枚举归档组，组内user在AI前；已见message_id复用其序号。因此active正式顺序严格保持不变，归档的合成序号不代表发生时间，档案排序使用原created_at/action顺序。旧文件没有插话时序，不声称合成seq是真实秒级时间；原created_at不改。
5. 旧pending/retry_input没有正式玩家消息，保留为legacy_retry_snapshot（仅旧attempt兼容字段，原协议/OOC/ID完整），不迁成已发送经历；pending先按旧recover语义转interrupted。显式重试时走旧协议适配，成功才把旧输入/单气泡转正式组，不能用v3读取旧结果。
6. requests保留原action/request/retry ID、fingerprint与协议身份；target_turn_id/result_turn_id改为对应group字段，archived_turn正文移到groups。旧失败且从未有正式输入的action允许无input_id并只带legacy_retry_snapshot，校验严格限定迁移旧attempt。
7. context_epoch=0，next_seq=全部已分配seq最大值+1。read_ai_seq初始化到迁移时最大active正式AI序号（没有则0），避免全部旧历史突然未读；这是保守不重报历史，不推断用户实际读过。归档AI不计未读，新增消息按新游标处理。
8. 重新validate_schema2并比较不变量：active正式ID/正文/可见性、全部旧归档ID、ledger及inverse、OOC/协议/冻结快照完全一致；formal_messages/记忆候选/召回结果除适配元数据外一致。旧合法数据若因新体积超限则停止迁移，绝不删原文凑容量。

真实迁移获确认后才包事务：同会话锁读取原字节与哈希→独立备份原文件并fsync且不覆盖旧备份→纯转换/校验→临时文件写/fsync/os.replace。备份成功而替换失败保留旧会话；替换成功崩溃后以schema2为准，不再重复迁移。两文件不是共同原子事务，但唯一权威路径始终只指向完整旧或完整新文件。旧版本读到schema2拒写；备份不纳入普通会话枚举，删除/备份清理单独说明，不能遗留默认导出正文。

## 12. B片实施顺序与验收出口

先reader/validator及纯合成迁移→共享ledger planner→输入接受/认领/组事务→timer/恢复/批操作→公共投影/容量与上下文接线。不先改生产默认schema，也不加载用户记录做试迁移。新测试临时目录可创建schema2；旧schema1回归必须继续通过。

最低测试：三态提交差异；候选不入formal；gaps末条账本；X/Y独立ID及一次认领；失败继续/重试不双回应；revision追加不误冲突而epoch变更拒迟到；两窗口同action幂等；容量预留；重生期间新输入拒替换；批撤回整轮；已读单调；崩溃恢复；旧pending/retry/OOC/归档、未知版本、迁移备份失败各点；旧memory/recall结果等价。

本合同无新增玩法问题。B片可按工程合同开始合成实现；真实迁移仍停在最终说明和用户确认门。若实现发现既有ID/归档约束与以上算法不兼容，先修合成适配和文档，不直接修用户数据。

## 13. 窄兼容片：转换后的旧attempt显式重试

实施状态（2026-10-08，B5b）：严格legacy_execution及快照身份验证、独立纯生命周期和后台服务分派已隔离实现。pending没有正式输入/空组；成功保留原ID单气泡提交、账本通知、批撤回及正常下一v3均有测试。Astra审阅发现真实config嵌套预算遗漏，已修新旧两路径并补预算回归。尚未启用生产构造器、API和UI，真实数据迁移仍需最终确认；本片不是C4完整交付或打包节点。

2026-10-08补充，仅覆盖转换保留的v1/v2失败/取消/中断attempt。不把旧attempt改成v3、不重新生成user/ai ID、不把旧pending输入提前正式化；成功才添加schema2单气泡组。之后正常新send继续v3/C4。现有group_service只执行C4、retry_group拒绝旧协议，这是真实待补缺口，不宣称已经兼容。

### 13.1 可复用与不可直接复用

- 复用旧context.build_context的任务身份选择、单current_user_message/current_ai_message_id、C3 OOC条件、预算裁剪顺序、opening/世界书/偏好/有界召回规则；复用旧PromptSlice与覆盖语义，不用C4 core解释旧输出。
- 复用transport.generate的v1/v2 ReplyPreview、一次调用/零自动重试；服务事件适配把字符串delta映射ordinal=0，不对旧字符串调用GroupPreview。
- 复用parse_result(raw, original_contract)、parse_annotations（仅v2）、共享plan_ledger；不调用plan_turn再迁移它生成的临时会话，也不伪造turns或拼接新组多个气泡骗旧校验。
- 复用schema2 repository原子事务、四槽、发布后保存核对、public_group、read游标及整批inverse；旧重试只有一气泡，gaps选择等价非流式立即送达，没有额外计时队列。

### 13.2 精确持久字段与身份约束

action.legacy_retry_snapshot仍为重试权威输入，严格字段content、mode、user_message_id、ai_message_id，可选ooc_note、reply_contract_id、context_contract_id。缺协议时沿旧默认V1/LEGACY解读；显式协议和最近旧attempt必须一致，bool(ooc_note)必须等价context=C3。OOC为空不能冒用C3，有OOC不能降级legacy/M3。

每次显式旧重试仍新增legacy_attempt=true的attempt，保留request_id、base_revision、status、created_at、reply_contract_id、context_contract_id、retry_of、retry_token。新增仅本兼容分支允许的legacy_execution对象，字段固定为group_id、context_epoch、history_cutoff_seq、display_mode。group_id本次由程序分配，失败重试不复用组ID；user/ai ID始终沿原snapshot。终态使用既有ended_at/error_code/committed_revision。

legacy_execution只表示待提交旧回复，不是正式组/输入；pending时不在groups建立要求input_ids已存在的空组，也不把snapshot复制到公共state。一个会话最多一个pending旧execution或忙碌新组。公共busy摘要可显示其group_id/request_id及generating，但不假称存在正式input_ids。

成功后groups新增complete单气泡组，group_id取legacy_execution.group_id，input_ids仅原snapshot.user_message_id，AI取原snapshot.ai_message_id；mode用原snapshot.mode，display按attempt快照。attempt继续标legacy_attempt，不变v3；group到该attempt的反向关系新增严格校验。failed/cancelled/interrupted的legacy_execution允许没有group，committed则必须有唯一对应group。

旧snapshot双消息ID必须互异，且在显式重试开始和提交时都不得撞正式/归档消息、参与者、组、action/request、ledger、opening或其它有效预留。历史失败attempt之间复用同一snapshot ID是重试链合法别名，不按不同消息重复计数；不同action不可共享这些预留。成功后清除action的可重试snapshot，attempt可保留有界审计快照，但不再构成可执行重试权。

### 13.3 重试前置和原子提交

显式retry须命中action最近failed/cancelled/interrupted旧attempt，retry_token重放先查身份再查CAS；已有成功result、被后续操作替代或原用户/AI身份冲突则STALE_RETRY。一次legacy执行占一个现有attempt和四槽之一，不自动收费重试。失败/取消后仍必须显式继续。

本兼容执行沿旧schema1的忙碌语义：开始前要求没有待回应schema2输入；pending期间新send及修改语境返回SESSION_BUSY并保留客户端草稿，不新增排队行为。这是一次旧attempt兼容路径，不改变正常v3连续批/连发规则；如此旧pending用户消息仍可保持“成功才正式”的承诺，无需预分配虚假正式seq或在新玩家输入后倒插旧话。若已有新正式输入，应继续正常v3，不强行执行过时旧retry；返回可解释的STALE_RETRY。

旧send的retry只允许位于最新已解决历史之后：除原旧失败记录外不能有后来已接受的新输入或新完成组。迁移后判断用requests原有顺序及group关联，不用迁移合成seq猜旧attempt时间。旧regenerate则要求target仍是最新完整active组、没有后续输入依赖；失败不改目标组。

提交先重验pending、epoch、owner、原协议、snapshot身份及无后续输入，再解析旧reply，构造独立的正式user/AI消息（原ID/正文/模式，提交时分配相邻seq和真实时间）。以本次完整允许正式来源+这两个待提交消息调用plan_ledger，current集合仅这两个ID，origin为新group_id；旧历史不能借dialogue_event变本轮经历。

旧regenerate先在临时上下文副本逆目标inverse并排除目标AI和目标输入；旧snapshot使用它原来预留的新user ID，不能把它改成目标输入ID。成功同一事务：逆旧账、目标组replaced、旧独占输入withdrawn、插入原snapshot用户消息和单气泡新组、应用新ledger/inverse/notice、标owner成功。失败/保存失败保留原组、旧输入和账本完整。原文/ID不按内容相同合并。

### 13.4 旧上下文构建不造假turn

新增build_legacy_retry_context读取schema2已结束组，将其真实消息按seq投影为history，当前旧snapshot仍用旧单输入字段。LEGACY不新增recalled_sources/context标记，M3/C3沿原字段；C3仅当前ooc_note，不泄漏历史OOC。重生成使用上述逆账副本；候选/归档/未来消息及未领取输入一律排除。

最小实现是从context.build_context提取可共享的“已有历史批+当前输入载荷→预算循环”私有帮助函数，schema1调用仍供应真实旧双消息批，兼容调用供应schema2真实多消息批。也可暂时保留窄适配构建器，但不得临时制造schema1 turns、把一组拼成假reply或重复user消息。旧history本来是消息数组，允许真实多气泡原文，不必更改旧输出/context协议。

返回的allowed_messages必须就是最终实际发送的真实原文投影；提交时按核心字段核对权威message，不能要求旧投影必有新seq，也不能因缺seq接受任意内容。预算当前输入/OOC不裁剪、历史按完整组裁剪；旧召回仍最多4条/4000字符，身份不扩权。偏好按执行时当前授权读取，沿现有旧retry规则，不恢复已撤销授权。

### 13.5 服务接线、取消与恢复

group_service.retry按原attempt身份分派retry_group或begin_legacy_retry；worker查询新增execution_for_request统一返回任务描述，不迫使current_attempt找到尚不存在的group。busy检测同时覆盖pending legacy execution，防止正常worker绕过它认领新输入。

_generate依任务协议选择build_group_context或build_legacy_retry_context；accepted保留group_id，仅预留一个旧AI ID，旧字符串预览转换为单气泡start/delta/end（只首次start、最终验证前end仍属临时），commit分别分派。广播仍只在保存成功后确认，预览失败不持久化、不入未读；新成功组可沿public_group原位替换ordinal=0。

cancel/close/start的终态函数同时覆盖无实体group的旧execution：仅标attempt失败/取消/中断，保留重试snapshot，不生成假输入/空AI/组。取消赢在调用前零调用；取消后立即retry/send仍走已修wake_pending机制。启动将pending旧execution标interrupted，不调用供应商、不自动创建组；成功后的旧组就是普通complete组，后续新send默认v3。

### 13.6 最小实施顺序和验收

先补legacy_snapshot协议/OOC/ID/owner与execution严格验证→纯旧上下文适配及parse/planner→无group旧execution生命周期→服务分派/字符串预览→隔离临时仓库回归。不能在这片修改生产路由、运行真实迁移或扩展显示需求。

验收覆盖V1/V2×LEGACY/M3及V1/V2×C3合法组合；丢失可选字段按旧默认、矛盾协议/OOC拒绝；原user/AI ID贯穿多次失败/取消/中断/retry；重复retry_token零额外调用；旧regenerate失败保留、成功原子替换、来源/高光/撤回准确；新多气泡历史进入旧单reply请求但不拼接假来源；流式失败无正式输入、保存失败无广播；取消前零调用/取消立即重试/重启零自动费用；兼容pending期间send忙碌不丢草稿；成功后下一正常请求v3。所有旧schema1测试保持不变，无新玩家产品问题。
