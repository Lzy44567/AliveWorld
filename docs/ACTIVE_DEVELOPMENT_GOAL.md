# Active development goal

Updated: 2026-10-13

## Current — 全游戏产品设计收口

2026-10-13当前：30记录实体卡/世界账本分责与上帝视角知情隔离；31补实体跨日事件与工坊完整创作流程候选、调用/等待取舍、验收清单。下一步整理开局到行动、后台变化、记忆与撤回的故事全流程，与创作流程对齐。仍仅产品设计；未进行模型实验或实现验证。

2026-10-12当前：用户讨论哪些设计可自主推进，明确故事内私聊价值尚未找到；29记录其后置及头像多人呈现不等于群聊引擎。按[设计收口计划](DESIGN_SYNTHESIS_PLAN.md)整理已有确认、端到端故事/人物/创作流程和UI原型，再形成总设计案；对产品关键取舍集中讨论，不微观反复确认。不编码。

## Historical — 分模块设计讨论进展

2026-10-12开局/UI补充：核对默认开场确由后端写入，29记录作者开局/辅助起点、UI整体原型及身份化头像/旁白/立绘资料设计。当前继续设计，不按新反馈立即改UI或写代码。

2026-10-12截图纠正：plotCompass主线剧情导向入口及存取已有，仅草案、未见模型接线；worldPremise为世界/开局概述。28补改名建议、父scoped样式未传入展开组件内部的白底问题。更正此前检索遗漏，不新增重复字段，本轮仍只诊断记录。

2026-10-12第十五轮：28补发展方向/剧情节点/偏好的协作、频率与影响分离及防重复候选；核对当前字段实际为worldPremise宇宙主导向，独立剧情方向入口未核实。下一设计简单偏好控制与方向字段语义，仍不编码。

2026-10-12第十四轮：用户要求综合叙事指导覆盖多种剧情，28记录通用发展/兑现原则、未来/正文/工坊职责及精简运行草案。隐藏身份转为一致性例子，不逐桥段加提示词。下一需讨论世界内概率与偏好取向的关系，继续设计不编码。

2026-10-12第十三轮：用户明确非所有世界数值化，27记录工坊可选指导生成通用规则及隐藏强者身份/揭露边界；自由叙事保留，默认关闭为建议。当前任务仍各模块设计，不转数值引擎或插件重构。

2026-10-12第十二轮：用户接受卡片积累方向；03补硬门槛/属性对抗/环境意外及锚点生成固定参数方案；26记录故事NPC提取为人设＋可选经历并跨世界载入。继续模块产品设计，不提前代码实现。

2026-10-12第十一轮：确认平静单候选及下一重要选择前停；03建议未来请求定规则→Python投掷→正文表达，记录小游戏方向。15核对通用预设载入未形成入口，已有内建体验预设不能冒充；继续设计，不编码。

2026-10-12第十轮：03记录用户的不同未来＋贝叶斯＋Python抽取，以及可选骰子/属性和硬要素；严格区分现有相对权重与待设计贝叶斯，不重复判定同一成败。24列世界知识收口项；下一设计候选为故事判定与剧情节点，尚未编码。

2026-10-12第九轮：核验DeepSeek前缀缓存文档，未发现支持多Key提升缓存命中的承诺；24记录局内卡片变更积累/批量整理候选，区分频率与重要性、隐藏与归档，不引入每轮全部卡片重写。仍处产品讨论。

2026-10-12第八轮：24补通用持续效果→状态、重要知识捕获门槛、正文候选→暗流合并建档的低等待方案。定向核对尚无正文实体候选接线；保持讨论，不自动开工。下一审阅这些分工及调用取舍。

2026-10-12第七轮：确认未到地图不触发，作者在世界书定义固定/可变结果；地图标记与资源线索为引导灵感。定向核对正文捕获和实体发现，24记录当前额外捕获调用与Overseer空库跳过，以及拆开实体发现/行动的改进候选。仍只设计。

2026-10-12第六轮：用户要求故事内复用正文请求报告冲突，不默认额外工坊审计；提示/自动停用/人工处理分类折叠。25记录原手稿地图→事件→能力变化的线性意图，游戏中是否必经仍待讨论。下一确认节点可偏离性和自动停用默认值；仅设计。

2026-10-12第五轮：多书结构与融合方向获认可；24补冲突检查责任/时机及非永久停用建议。25记录复杂文稿→世界包工坊候选及现有外部格式导入代码事实。下一讨论冲突默认处理和文稿剧情节点语义；不转入编码。

2026-10-12第四轮：确认逐条/统一接受拒绝、编辑删除及带要求AI重写；确认隐藏设定默认不泄漏、可主动全知审阅。24新增简洁审阅UI与多世界书候选：主书/知识书/自动书兜底、主题归属、冲突融合和跨书移动。下一讨论多书结构及冲突默认；仍未编码。

2026-10-12第三轮：局内设定默认自动写入＋简要轻提示，可开详细逐条提示或人工弹窗审阅；已成立规则变化人工决策默认关闭；公理双用途标记获确认。撤回/分支需同步世界书，稳定来源及修订关联为设计建议。下一明确拒绝已成立事实时的处理、多书写入目标与隐藏信息展示。

2026-10-12第二轮：正文自然推进＋并行工坊补全为用户确认方向；技能/阵法当前效果与底层规则改变分开，来源失效需精确更新；公理可同时承担创作约束和世界规律。24文档已记录确认项及候选来源关联方案。下一讨论补全档位、自动生效权限和公理双用途；继续只做设计。

2026-10-11用户确认先完整讨论模块、持续记录，再形成游戏详细设计案并统一安排实施。当前第一模块见[世界知识与变化](features/24_world_knowledge_product_design.md)：区分既有规则、发现/补全设定、世界内能力造成改变。NPC重复卡和实体未收录作为待诊断体验记录，不自动转入修复。下一步讨论该文档六项产品选择；角色摘要B继续暂缓编码。

## Historical — 全模块设计与灵感清点

用户要求先汇总全部设计，为整体产品设计讨论准备资料。[设计总索引](DESIGN_CATALOG.md)按模块归并241项，分别记录类型、设计成熟度、实现/验证状态与建议优先级，保留小灵感、未决问题和被替代方案。此次仅文档整理与定向入口核对，不是全功能重新验收，不代表所有设计已冻结。

下一步由用户审阅总索引，再决定正式版玩家目标与设计顺序；角色摘要B暂不实施。已完成的共享规划A保留，无版本、包或远程发布变化。

## Historical — 共享压缩规划A完成，候选下一为角色摘要B

用户要求继续并让Astra小范围决策；按[22y](features/22y_shared_compression_character_stage.md)调整为先复用上下文压缩，不先重构存储。A已实现：独立纯水位规划函数，故事行为不变，44项专项通过、2000次旧新结果对照一致。未新增模型调用或改真实数据，未升版本/打包/发布。

下一玩家目标B：schema2当前角色会话专用摘要＋近期完整组＋M2/M3。先确认摘要调用的会话授权/费用开关，补缓存与来源失效、提交及上下文接线短设计，然后实施；默认候选关闭，不继承故事或主动联系授权。当前尚未接角色摘要，不把A基础片称为功能交付。存储扩容与角色质量评价分别后置，不丢弃原文或提高硬限额。

## Historical — 已冻结角色阶段收尾，停在新设计边界

2026-10-09用户要求目的模式推进到功能设计边界。核对22n/22w/22x、领域/API/UI及测试后，M2、M4a、M3、C3、C4、C5-A/B均已实现，没有本轮已冻结但未实现的编码项。补正总纲的旧状态，专项103项通过（19.709秒），现有c5b-preview ZIP SHA256复核一致；没有核心代码变更，不重复构建相同应用。

下一步需要新设计：P1候选长聊容量（先压力评估，后存储/恢复/迁移合同）；P1角色质量案例与评价标准。真实旧会话升级入口、费用测试和线上发布仍独立授权。不会把长期性格、群聊、关机后台或通用agent加入本轮。

## Historical — C5-B批量启停与每日免打扰交付

目的模式本轮目标：完成22x-B，验收并生成独立本地包；不发布GitHub、不调用付费模型、不修改真实玩家记录。列表明确勾选/全选现有会话、费用确认、逐项结果和对称关闭已实现；每日一段本地时间免打扰、跨午夜、完整闲置重等及旧计划取消已实现。只增加独立时间计算与小列表面板，不建通用调度/批任务框架。

819 Python、145 Node、169模块构建、最终Edge7通过；浏览器初次暴露表单刷新覆盖输入，已修字段级同步并重建，wide/narrow截图已检查。独立dev.19-c5b-preview本地ZIP编译及归档校验完成，hash见TESTING，旧包保留。目的模式目标完成，停在C5已设计范围/本地打包节点；未启动冻结EXE、付费测试或线上发布。长聊扩容、关机后台、文学质量仍各有设计/验收边界，不自动追加。

## Historical — C5当前会话主动联系闭环

22x交付片A已实现并验收：当前会话费用确认/授权→下一正式玩家输入开始周期→本地闲置/编辑租约→一次有限规划→真实无input主动消息组→未读/撤回→新输入取消。领域、调度/额度、上下文/提示词、客户端控制器和面板分别拥有职责；核心service/runtime仅接线。默认关闭，仅服务运行时有效，旧会话不自动转换；主动组首版原子送达且不提供重生成。

813 Python/144 Node、168模块生产构建及C4/C5浏览器6项通过；宽窄截图已检查。独立dev.19-c5-preview包编译/归档校验完成，详情和hash见TESTING；旧包保留，未启动冻结EXE或发布GitHub。下一片B为现有会话批量启停、每日免打扰；未实现，不扩成关机后台或通用agent。不擅升版本或付费测试。

## Historical — delivery speed / proactive-contact design

用户要求减少防御性编程，已有独立校验模块保留；继续推进下一候选主动联系。先核对实际改动并将send/batch/retry请求规范化集中`group_requests.py`，不更改业务、模型调用或存档格式；不为此次检查发起全仓审计/重构。63项相关Python通过（12.874秒）。下一冻结主动联系最小玩家闭环：UI授权→一次规划→闲置送达→新输入取消→列表未读，随后直接实现；没有玩家输入的主动组必须真实建模，不能伪造消息。当前设计由Astra负责，未完成前不冒称主动联系已实现。效率规则已写入AGENTS，旧验收包保留，不重新打包同一行为。

## Latest continuation — C4交付收尾

用户允许继续；按[22w](features/22w_character_next_phase_and_upgrade_boundary.md)补独立备份事务并只在临时目录验收，不读/转实际玩家会话、不接自动迁移入口。旧会话继续原路径，真实升级不是新会话验收包前提。下一轮设计候选为有限主动联系、容量扩展与角色质量案例，不在本轮自动转向。版本选择已向用户提出，旧包和远程均保留；本片测试/包证据依TESTING实际结果记录。

收尾完成：11项新备份测试、全Python785/Node137通过；165模块构建及本地主程序/更新助手与ZIP校验通过。独立`dev.19-windows-x64-c4-preview`验收ZIP已生成，内部版本不擅改、旧包保留；无本轮冻结桌面运行/真实数据转换/付费质量/GitHub证据。下一步先确认版本命名或收集包验收，再对22w主动联系候选过设计门，不自动编码。

## Current — C4 bound streaming / multibubble implementation

Latest user definition supersedes the historical display question below: streaming and progressive character display are one feature, with no independent animation switch; streaming and whole-bubble gaps are mutually exclusive, or both off. Astra completed [22u](features/22u_character_display_and_multibubble_execution.md) and [22v](features/22v_character_message_groups_storage.md), both read fully by the main agent. No new gameplay question is needed. Goal mode continues A → B → C → V, stopping at the verified real-session migration/packaging boundary, not after a decorative switch. No new stop button, forced interruption, C5, capacity expansion, paid call or remote publication.

A/B/C are implemented in source: v3 lexer/strict validation, schema2 group lifecycle, shared runtime/API, detached subscriptions, keyed real bubbles, queues/read and old-format branches. Existing records are not converted. The earlier A/B headings below are historical implementation evidence, not the current next task.

### V / new-conversation activation — 2026-10-09

Recovered the completed fixed-build HTML report after the process handle disappeared:42 expected/42 total, zero unexpected/flaky/skipped; character-groups3, old character17 and full-player22. This is actual report evidence, not a guessed process result. Following that gate, UI creation now explicitly requests schema2 and attaches its subscription after create. Existing records retain their real schema. Old browser tests explicitly create1 (including lost-create response test) instead of silently upgrading all fixtures; C4 has an independent real new-UI test with an untouched old-record comparison.

Activation narrow run6/6 passed (1.1m),137 Node pass (832.8412ms),165-module build pass (1.68s). Final43 browser rerun passed (384891.446ms / 6.4m), saved JSON report has expected43/skipped0/unexpected0/flaky0. Full Python774/774 (44.541s) remains the unchanged-backend final evidence. The current implementation/V stage is verified and stops at the documented real-record migration confirmation gate: the conversion remains pure/synthetic and the real backup/replace operation is not installed or executed without confirmation. No EXE/version/paid-provider/remote/player-file change. Next human task: confirm whether existing role conversations should be upgraded, which data directory/sessions are in scope, and then authorize the backed-up conversion/packaging slice; do not substitute C5 or a new feature.

Historical headings below do not override this contract.

### C3 actual bubble UI / V in progress — 2026-10-08

Final rebuilt narrow check after both race fixes: all137 Node (846.9907ms), 165-module build (1.68s), C4 Edge3/3 (25.1s) pass. First full42 run had40 pass/1 read-CAS failure/1 skipped, so it is NOT full success; restart complete V on this fixed build. New UI schema2 creation still gated until V, no player migration or package.

Schema2 now renders formal and temporary rows once, keyed by reserved message ID, with direct text updates and no replay animation. Two display switches are mutually exclusive or off, future-attempt only; queued send remains available and existing cancel is generation-only. List unread uses server cursor; capacity labels logical groups. Separate C4 fake provider and three actual Edge scenarios use explicit synthetic schema2, while old fixtures stay schema1. First targeted3/3 passed; preliminary full run exposed a read-ACK/CAS race during rapid undo. Fixed command/memory mutation ordering and added deterministic tests, plus stale precommit GET protection. Final rebuilt browser V still pending; do not claim the first targeted result proves final build. Full Python774/774 (44.541s) passed. New UI creation still default1 until V/activation, no real migration/package/version/remote change.

### C2 schema2 client state — 2026-10-08

Separate group controller now owns visible-session subscriptions, quick JSON commands, same-action outcome checks, per-request/ordinal reserved-key previews, authoritative replacement, whole-group pages and server read acknowledgements. Switching/hiding detaches only; v3 busy can queue new input; legacy busy rejection preserves paired drafts. Retry never consumes new drafts, previews never become history/read, and pagination is revalidated rather than retaining withdrawn rows. Old schema1 paths remain unchanged. Ten new state tests and full135 Node pass (813.1792ms); no new Python/browser/package evidence. Next actual bubble/UI integration and complete V; new UI schema2 creation remains gated, no real migration/version/remote change.

### C1 client event stream and display preferences — 2026-10-08

Added separate group JSON/read/page API methods and long GET subscription parser (not legacy fetch-POST SSE), with safe shared errors, strict session/connection/event/request identity, UTF8/byte bounds, reserved IDs and multiple requests per connection. Abort detaches even while waiting; no model cancellation/retry command is sent. Existing schema1 methods remain unchanged.

Interaction preference version2 explicitly stores stream/gaps/instant, two mutually exclusive switches or both off, without a typing option. Version1 maps stream→stream and non_stream→instant in memory, never overwrites on read; old get()/delivery API shape remains compatible. Nine new tests, full125 Node pass; build evidence in TESTING. These are client foundations, not visible C4: next integrate schema2 store (queued commands, subscriptions, authoritative reload/read, stable per-ordinal previews) and real UI. No new UI schema2 creation until that branch and browser V work. No package/version/provider/player migration/remote change.

### B8 actual HTTP / application composition — 2026-10-08

Main now owns the injected mixed-schema runtime lifespan; all old/new routes select the same repository/services and four slots. New schema2 is explicitly constructed (no persisted conversion), while omitted/explicit1 creation keeps old fingerprints/response protocols. New sends/retries/batch commands return quick JSON; long bounded GET SSE is detached from workers, registers before ready, assigns stream_id/event_seq and actual owner IDs, and drops only subscription on disconnect/overflow. Group pagination/read/auxiliary management dispatch by actual supported schema. Unknown formats stay read-only, including repositories intentionally supporting only1 in old tests. Tombstone delete replay remains204.

New route/subscription acceptance includes real ASGI disconnect, startup/multiworker refusal, privacy, display/delivery conflict, read monotonicity, retry idempotence, main injection and old protocol/file preservation. Astra review was interrupted by usage limit and is NOT a completed review; design remains frozen, main-agent contract review/tests continue. Exact full-suite evidence in TESTING. Frontend still old: next C1 client subscription/three-state preference and schema2 store/UI branches; new UI explicit2 creation waits until complete browser V. No package/player migration/version/paid-provider/remote changes.

### B7 shared provider budget and lifecycle foundation — 2026-10-08

Implemented injectable mixed-schema runtime, shared four-slot admission for synchronous legacy and asynchronous C4 workers, single-loop guards and lifespan factory. Cancellation before/after slot transfer returns ownership; legacy recovery explicitly skips schema2; shutdown interrupts pending old requests and releases unexecuted reservations. Astra found and the main agent fixed C4 retry/regenerate waiting for a slot at shutdown: reserved generation becomes interrupted while delivering tails/queued inputs stay untouched. Shutdown persistence errors are exposed after other tasks/slots are cleaned. Multi-process C4 start/write/subscription is refused. This module is not yet wired to production main/routes: do that together in the next HTTP slice so old/new routes cannot use independent budgets. Eleven new tests and full757 pass; no UI/package/player migration/version/remote change. Next: actual-schema API dispatch, quick JSON commands and detached bounded SSE subscription, read/groups, then frontend and V.

### B6 public records and auxiliary mutations — 2026-10-08

Astra froze22v section14 and the main agent read it fully: actual-schema dispatch, explicit new-schema creation only with the matching UI, no automatic player migration, JSON commands separate from long SSE subscriptions, shared provider slots/lifespan, source/notice/read and mixed-schema acceptance. Implemented isolated schema2 detail/summary/action projections, whole-group pagination, owner resolution for merged inputs, shared pure retry eligibility and auxiliary metadata/memory/source operations. Candidate tails/import metadata/inverses remain private. Title and notice acknowledgements may run while busy without changing context_epoch; semantic mutations require no generation/delivery/unanswered inputs. V3 batch-end notice and archive-safe acknowledgement now work.

Astra found and the main agent fixed an action/attempt identity mixup: undo must expose its control attempt, while explicit old request queries must not carry a newer group/notice. Added regressions. Next verifiable slice: mixed-schema runtime with shared four slots and app lifespan, then JSON actions/long SSE/read/groups HTTP wiring, C frontend and full V. Routes and new UI creation remain unchanged; this is not a package/migration node. Evidence in TESTING; no version/provider/player-data/remote change.

### B5b legacy execution/service — 2026-10-08

Converted old attempts now have a strict, nonformal execution reservation, explicit retry/terminal/atomic single-bubble commit and protocol-aware background service dispatch. Original user/AI IDs and v1/v2/context/OOC remain frozen; failed/cancelled/interrupted execution adds no formal messages. Legacy regeneration keeps the target until success, then reverses ledger and replaces its exclusive input atomically. Startup interrupts pending execution without a model call. Retry-token replay, pre-provider cancellation, source/highlight notice, batch undo and next normal v3 request have synthetic regressions.

Astra read-only review identified a P1: both C4 and legacy builders were receiving the whole connection config instead of nested budget_options. Fixed both paths and added real-config-shape window/reserve and zero-call overbudget tests. This service remains opt-in; production/API/UI activation and full V are next, not a packaging or real-player migration node. Final verification evidence is recorded in TESTING; no version/provider/player-data/remote changes.

### B5a legacy-context preparation — 2026-10-08

Astra added22v section13; the main agent read it fully. Implemented shared old-protocol context budget assembly with actual message batches, plus isolated legacy-retry context over true schema2 history. It keeps original user/AI IDs, v1/v2 and LEGACY/M3/C3 identities, OOC permissions and old prompt override selection; no synthetic turns or joined AI text. Schema2 capacity has an explicit version2 logical-group report, while old readers remain unchanged. New10 tests cover six protocol/context combinations, defaults/conflicts, regenerated history, whole-group trimming and reserved/failed capacity.

This prepares but does not execute old retries: legacy_execution strict validation, pure retry/commit lifecycle and service dispatch remain next. Then production/API/public projections, frontend and completeV/migration gate. Do not call B5a compatible retry completion or a packaging node. No player data/provider/API activation/version change.

### B4 server-owned scheduler progress — 2026-10-07

The opt-in schema2 service now runs actual asynchronous group workers: four provider slots reserved before input claims, one call per bounded group, realtime preview events, persisted gap delivery without subscribers, batch-end queued-input coalescing, monotone read acknowledgement and group actions. Candidate tails/private ledger never enter public events. Persistence failure is not broadcast as success; undelivered valid tails remain recoverable. Cancel then immediate retry/send has an explicit lost-wakeup regression.

Startup recovery delivers only already-generated tails; old queued inputs do not trigger new model charges. New explicit input during recovery authorizes normal continuation. Pending generation becomes interrupted, with no automatic retry. Astra identified both the cancellation wakeup and restart-with-queue hazards; fixes and regressions were added. Production constructors/routes remain unchanged and no real sessions were converted. Next is legacy-attempt execution compatibility and schema2 API/public projections, then frontend streaming-in-bubbles, display switches and full browser/migration verification. This is not the full goal or a package node.

### B3 multi-input context progress — 2026-10-07

C4 context assembly is now implemented in isolation: independent claimed messages/OOC links, immutable cutoff, whole completed-group history, bounded exact-source recall, world/preference budgets and a separate four-slice prompt identity. Old schema1 creation/service/overrides remain unchanged. Future and unclaimed inputs, withdrawn/replaced answers, candidate tails and historical OOC cannot enter the new request. Regeneration reverses old ledger before context selection. Astra's read-only review found no blocking defect; requested combined queue/recall-budget coverage was added.

Next verifiable slice is the actual background service scheduler: single provider call per group, stream events, persisted delivery/queue ownership, failure/explicit continuation, reopening/read cursor and legacy-attempt adaptation. Then wire frontend in-place bubbles and mutually exclusive display controls, run full browser validation and reach the explicit real-session migration/package gate. B3 is not complete C4 or a new EXE; do not stop or shrink the goal here. Evidence is recorded in TESTING.

### B1/B2 isolation progress — 2026-10-07

Schema2 strict validation, formal/candidate projections, pure deterministic legacy conversion and aggregate mutations are implemented in isolated modules. Repository injection defaults to the old schema1 validator, so live conversations/default creation stay unchanged. Stream/instant atomic batch, gaps first/next delivery, batch-end ledger, explicit continuation after failure, bounded queued-input prefix, stable retry, group undo/regeneration, read cursor and startup rescheduling have29 synthetic tests. Shared envelope and ledger validation retain the old path. Astra review's concrete interjection/undo/retry-capacity defects were fixed and regression-tested. No real player files, provider calls, route/UI activation or EXE change.

Next verifiable slice: C4 multi-input context/recall/world/preference/budget assembly and independent service scheduler (real background delivery/queue ownership), legacy-attempt retry adaptation, then frontend mutual switches and in-place previews. Full objective remains active; neither A nor B pure transactions are a completion/package boundary. Final full Python678/678 (29.168s) passes; latest full-run evidence is in TESTING. This slice has no new UI/build/browser/package evidence.

Current discussion supersedes the stop-control proposal below: user does not recommend adding a stop button because players cannot react quickly and truncation adds lifecycle complexity. Requested Astra to refine optional provider streaming, local character-reveal animation, and once-generated bubble groups with deterministic length-based gaps. This turn is design-only. Do not add a new stop control, assume it is required to finish C4, or delete the existing character cancellation implementation without separate authorization. Design must prevent repeated animation/double delays and separate unvalidated preview, official delivery and read status. Historical notes below are not current authorization.

Astra refinement completed in22t and reviewed in full; main review removed the draft's repeated automatic-truncation recommendation, retaining the already confirmed short-burst completion then response to accumulated inputs. One remaining display question: when local animations are enabled, buffer/validate before showing rather than also display the same provider preview. Timing/array schema/storage migration still require concrete implementation design, not more approval of interruption policy. This documentation-only slice has no new runtime tests, code, package or version changes.

Latest clarification: pacing authority resolved to deterministic content-length timing plus a player on/off toggle, not model seconds or player speed slider. Exact delay/cap remains design work; each-character0.1s was an example.22t section11 distinguishes generated versus delivered bubbles and an unobtrusive composer stop control (not between messages). Story/workshop stop gap is recordedP1, not silently implemented or substituted for C4. Current turn updates design only.

## Latest — C4 conversation guidance complete, product choices remain

User authorizes Astra design and continued coding, but pacing authority remains undecided. Astra task was quota-interrupted without a file; explicit retry completed [22t](features/22t_character_conversation_c4_design.md), main agent read it fully. Only C4-0 is independently frozen and implemented: short conversation guidance in existing M3/C3 core, single reply, no new request/schema/UI/queue. Current input/evidence/contract/legacy/override behavior retained. Seven new tests and full Python637/637(23.641s), Node116/116, visibility and160-module build passed; related EdgeC3/M3 2/2(1.1m) passed. No new full39-browser run or real-model quality claim. Next: resolve pacing authority and ordinary interjection versus immediate interruption, then finish the multi-bubble migration/delivery plan; neither selection nor candidate schema is silently frozen. C5, capacity, version/package/remote remain out of scope. Existing packages unchanged. Use this heading over historical boundary records below.

## Current boundary — C4 message-group delivery design

Latest user clarification supersedes unconditional interrupt-cancel and restart-no-send proposals: distinguish continuous short bursts, waiting for the player, and responding then returning to a topic; minimum visual gap0.1s, one call per group, group-level undo/regenerate, durable unread/background/reopen behavior.22s section7 records current requirements, role-guidance implementation versus gaps and process-exit limits. No code changed. Next design must integrate role response strategy and delivery behavior, not merely schema/animations. Ordinary interjections versus corrections/stop and offline recovery remain to be specified.

User authorizes staged continuation to the design/package boundary. C3 is committed as `a5d202e`, worktree was clean. Read the existing22m/22n product requirements and inspected actual single-message validation, plan/ledger inverse and public preview paths. [22s](features/22s_character_message_delivery_design_gate.md) records the C4 design gate, partial-delivery/op-dependency risks, acceptance and C4-D→A→B→C→V→package sequence. This is a documentation-only boundary review, not C4 implementation or new runtime acceptance. Next verifiable artifact is a complete frozen C4 protocol/storage/delivery/recovery contract. Stop before changing runtime schemas, C5, version, package or remote state; do not substitute frontend delays for authoritative delivery. Existing630/116/39 results belong to C3, not this document review.

## Completed — C3 structured OOC and single-step role agency

User continues after completed M3. Main agent fully read Astra [22r contract](features/22r_character_ooc_c3_contract.md); independent review added stored OOC/owning-context consistency. Delivered one-turn structured OOC accompanying dialogue, immutable paired inputs across retry/regeneration/recovery, source/history/world-match isolation, required budget, independent context identity, dual-draft composer and distinct historical notes. No pure OOC, persistent controls, paid analysis, C4/C5, capacity, version/package/remote change; normal no-OOC requests remain M3, strict reply.v1/v2 unchanged.

C3 completed: final Python630/630 (23.250s), all Node116/116, visibility and160-module production build passed. C3 Edge1/1 (23.3s), initial full Edge39/39 (5.4m), final rebuilt full Edge39/39 (5.3m, C3 23.5s) all passed with no skip. Latest wide1600x1000/narrow520x900 screenshots inspected; no horizontal overflow. Independent Astra audit found no remaining actionable P0/P1. Existing541.51KB bundle warning remainsP2; real-model naturalness/OOC semantic leakage unverified. Docs/player guide/categorized changelogs updated and source changes delivered to local Git. No player data, paid calls, version/package or remote changes. Goal stops here: next independent C4 message-group/partial-delivery contract, thenC5 bounded contact. Do not silently start either.

## Completed — M3 local cognition and bounded source recall

2026-10-06: user authorizes goal mode, design then implementation. Main agent read the complete Astra [22q contract](features/22q_character_cognition_m3_contract.md). Deliver a rebuildable session-local ledger index and at most4 whole linked old formal messages/4000 Unicode characters, final budget/evidence closure and independent frozen context identity, compatible reply.v1/v2, public index/recall UI and isolated full acceptance/local Git. Do not infer semantic preference conditions with lexical matching, share across sessions, expand capacity, add model calls, bump version, package or publish. Next verifiable slice: backend/context/API and frontend index/source report, then lifecycle/privacy/browser/visual verification. C3/C4/C5 remain independent unfrozen engineering gates.

M3 completed: final Python606/606 (24.226s), all Node109/109 (character57), visibility and158-module production build passed. Final complete Edge38/38 passed (5.3m), including actual source projection beyond20 turns, public index/source filtering, source links, draft preservation, old-source revision and undo/reload; wide1600x1000/narrow520x900 latest screenshots inspected. Initial new test fixture errors and small-screen selector timeout were repaired without relaxing runtime policy. Source/shared-group first-selection order and budget closure verified. Existing537.38KB bundle warning remainsP2. Goal audit in22q maps full requirements to current implementation/evidence; no paid model, player data, capacity, version, package or remote changes.

Next verifiable design gate is C3 structured OOC and role agency: preserve the already chosen expandable textbox above the composer, freeze dual-draft/pending/retry/history/authorization contracts before code. Then C4 message groups and C5 bounded contact; do not silently implement these or claim complete companionship/semantic psychology at this M3 boundary.

## Completed — M4a capacity diagnosis to the next design gate

User explicitly enables goal mode after confirming22p is ready for implementation. Final outcome is a truthful session-local capacity view and non-blocking near-limit warning, not unlimited memory. Implement the pure report, read-only GET, guarded frontend refresh and foldable panel, then isolated narrow/full/browser acceptance and categorized docs/local Git. Do not raise constants, delete/archive source records, introduce paid calls, bump version, package or publish.

M4a completed: unchanged hard limits extracted for validation/report consistency, private storage dimensions only produce combined pressure; public turn/action/attempt counts retain their distinction. NarrowPython10/Nodecharacter50 and M4aEdge1/1(9.7s) passed, wide1600x1000/narrow520x900 visuals checked. tools/run_checks.ps1 succeeded; finalPython581/581, allNode102/102, visibility,155-module production build and completeEdge37/37(5.1m) passed. Final Python rerun after adding the hard-limit retry assertion passed in24.228s. Existing527.35KB bundle warning remainsP2; no paid calls, player data, package or remote changes.

Goal reached at this slice boundary: capacity view/near-warning/read-only API/accurate lifecycle explanation are delivered, no storage expansion or automatic summarizer. Next verifiable work is the independent M3 local cognition/source recall contract in22n, followed by C3 structured OOC, C4 message-group delivery and C5 bounded contact contracts. Existing user choices need not be re-asked. Stop implementation before these unfrozen protocols; do not quietly start storage migration or call this complete character companionship.

## Completed — character chat M2 design and staged implementation

Latest user authorizes Astra to complete the related character-chat designs, then 6.1 Sol to implement approved slices until the design boundary. Final goal is the basic one-to-one character loop and companion memory, not immediate real-model experience testing. M1 remains complete; first next slice is M2 automatic sourced importance/highlights after its protocol gate.22m records agency/OOC, multi-bubble and proactive-contact directions; ordinary parentheses do not prove OOC, roleplay statements do not authorize real-user profiling. Proactive contact is default-off, once-per-idle-cycle planning with prewritten delayed messages rather than provider polling; recent editing activity suspends idle time but a leftover draft does not, per-role contact caps and global caps/token budget are required. These are design requirements, not a running scheduler. WeChat channel remains future and unverified.

Design review must separate frozen M2 from remaining capacity, input identity, grouped delivery and paid-background gates. User answered the product choices: a small button expands an OOC textbox above the dialogue composer; proactive contact authorizes only the current session. Ordinary parentheses remain in-character actions. These choices are recorded in22m/22n, not implemented as part of M2. Preserve existing strict v1, request-frozen protocol, reversible provenance, model/AI-private visibility and current capacity until a separate migration gate. Implement and verify cohesive backend/API/store/UI slices, update categorized docs and Git, then stop at the next unconfirmed gate. No version bump, package overwrite, paid model calls, player-data access or remote publication is authorized by this round.

M2 completed: full Python571/571, all Node99/99, visibility,153-module production build and complete Edge36/36 (5.2m) passed. M2 browser1/1 (21.5s), wide1600x1000/narrow520x900 visual checks passed; source/selection/manual protection/draft/reload/regenerate/undo verified. Old prompt registry assertion updated for explicit22 slices and independent v2/v1 ordering; not a relaxed parser. A Windows asyncio10054 warning occurred during deliberate cancelled browser connection, corresponding test and final suite passed; existing522.13KB bundle warning remainsP2. No paid calls/player-data/remote changes. Real-model semantic quality is unverified.

Next verifiable slice: Astra22p M4a capacity diagnosis contract is frozen, implementation not started. It adds truthful bounded capacity visibility, not storage expansion or unlimited memory. M3/C3/C4/C5 need separate engineering contracts; OOC UI/current-session permission choices are already answered and must not be re-asked. Stop this M2 slice here; no version/package action. Existing M1 ZIP remains older than this source slice.

## Completed delivery — C1/C2/M1 local acceptance package

User requests continuous progress until the design boundary and packaging. M1 is complete; M2 remains unfrozen, so this delivery does not invent highlight protocols or global profiling. Local packaging is now authorized, remote publication is not. Version question is unanswered: keep public VERSION dev.19, build a separately named M1-20261005 acceptance ZIP with a validated ArchiveSuffix rather than overwrite the old dev.19 archive. This is a package identifier, not user approval of dev.20 or a normal update-channel release. Update the bundled player guide, rerun full acceptance, compile main EXE/updater, verify privacy/embedded frontend/modules/overwrite preservation, preserve old packages/UserData, then Git evidence. Real-model quality and desktop launch remain user acceptance.

Completed: Python553/Node90/build151/Edge35 (3.8m) rechecked, actual Windows main EXE and updater compiled, package privacy/version/overwrite-UserData checks passed. Frozen archive has14 character modules including memory/preferences/world_context and no project test modules; embedded frontend exact hash and all three bundled guides verified. PackageOnly stale native exit-code bug found and fixed, then tested with deliberately inherited LASTEXITCODE=1; invalid ArchiveSuffix path rejected. ZIP `release/AliveWorld-1.6.0-dev.19-windows-x64-M1-20261005.zip`, SHA256 `08f697eff346e85f68c88b717d3b90337e60ce066e5918b927b665aeef576b02`; old dev.19 SHA256 remains954d4b91ee6d1ce82307bf3c344986a7a44be5703ed5d885e6275f8341e5dc4b. At design boundary: stop before M2 automatic highlights; real desktop launch/model quality and new version naming are user acceptance/choice. No remote action.

## Completed slice — M1 sourced recall and player protection

User authorizes Astra design then development. Main read the complete [22l contract](features/22l_character_memory_m_contract.md). Adopt conservative session-local character knowledge, not a global real-player profile. Final goal of M is companion continuity; this slice only delivers deterministic old-topic recall, eight public important roots, safe associated sources, request-scoped public report and non-destructive correction draft. Existing reply.v1/evidence permission and capacity limits remain. No extra model call, version/package/player-data/remote changes. Next verification: policy/transaction/API/store, isolated full regression/browser and wide/narrow visual checks, then coherent source commit. M2 automatic highlights remains a separate protocol gate.

M1 completed: Python553/553, Node90/90, visibility,151-module production build and full Edge35/35 (3.8m) passed. Standalone M1 browser1/1 (48.4s), wide1600x1000/narrow520x900 visual checks passed. Old sidebar test heading was updated to the intentional new heading after the first full run failed; final full run passed with no skipped tests. Source-only delivery, existing dev.19 archive unchanged. No P0/P1 found in this bounded slice; semantic quality/actual companionship still requires real-model acceptance. Next verifiable slice is M2 automatic highlight extraction/withdrawal/correction/notification and reply.v2 contract design, not silently raising capacity or enabling global profiling. Keep the current version until package scope/version is authorized.

## Historical design gate — M character long-term memory

User confirmed stable companion continuity first, optional realistic fading later, automatic highlight selection with non-blocking notice and player correction, protected explicit preferences/boundaries/promises/relationship changes.22k now separates these confirmations from proposed highlight signals and detailed user-profile scopes. Next product choice: session-local role-aware profile versus global actual-player profile; then freeze extraction timing, provenance/permission, budget and recovery. Not a frozen engineering architecture or coding authorization. C1/C2 remain complete source slices; no runtime/version/package/remote changes during this discussion.

## Completed slice — C2 opt-in confirmed preferences

User continued after C1; follow22j. Adopt the previously stated conservative default (off, per-session manual opt-in), not a claim of an explicit option answer. Read-only confirmed preferences, independent sensitive authorization, persisted revision-guarded settings, frozen current request and renewed authorization on explicit retry/regenerate implemented. No private-chat analysis, stored preference copies, memory work, version/package or remote actions. Python preference/routes18 and Node character24 narrow checks passed; full Python542/Node87/visibility/149-module build, standalone Edge1/1 (13.0s) and full34/34 (3.0m) passed. Wide/narrow UI visually checked. dev.19 ZIP hash remains unchanged; C1/C2 are source-only additions after its build. Next verifiable gate is real-model quality/package acceptance or the separate M sourced-memory design, not automatic M implementation or rewriting the dev.19 archive.

## Completed slice — C1 worldbook continuity and observable matching

User continued after dev.19 delivery. Follow22g/22i: first bounded current-input + recent public formal-message worldbook matching, safe request-scoped report and UI explanation, no extra model calls or data migration. C2 preference default is awaiting a product answer and is not implemented in C1; M remains a separate gate. Final C1 goal is source delivery with narrow/full/browser verification and Git/docs evidence, without a new version/package/GitHub release.

C1 completed: Python531/531, Node85/85, visibility and148-module production build passed; full Edge33/33 (3.0m), final standalone worldbook check1/1 (13.4s). Expanded matching reports visually inspected at1600x1000 and520x900. Request/visibility/budget/withdrawal ownership verified using isolated synthetic data, no paid calls. Source delivery only; dev.19ZIP unchanged. Next gate C2 requires the user's default preference-card choice and its persisted authorization/retry contract; M is not substituted for it.

## Completed delivery — B2 through dev.19 local portable package

User authorized 1.6.0-dev.19 local EXE, preserving dev.18 and no GitHub publication. A/B1/B2 delivered: messenger UI, explicit author opening, independent character fields/examples, shared target CAS and atomic draft/publication recovery. Source commit aa37ef4. Final Python522/Node82/build and complete Edge33/33 (3.4m) passed; wide/narrow fields visually checked. Windows main EXE/updater built, package privacy/version/overwrite preservation and embedded frontend exact hash verified; ZIP SHA256 954d4b91ee6d1ce82307bf3c344986a7a44be5703ed5d885e6275f8341e5dc4b. No player data or paid API calls. Desktop EXE launch and real-model quality remain player acceptance, not claimed automatic evidence.

Next verifiable gate: user tests this local package's input feel/opening/example behavior; record quality feedback before choosing C world/preferences or M memory design. Neither gate was silently added to this release, and no next implementation is automatically authorized by completion. Below sections are historical slice records.

## Completed slice — B1 optional author opening; next B2

B1 completed (2026-10-04), following22h: optional explicit opening, atomic/frozen storage, safe context projection, no formal turn or ledger evidence, creation retry identity, visible opening and summaries. Python511/511, Node79/79, visibility check,144-module production build and complete Playwright/Edge33/33 (3.0m), wide/narrow screenshots inspected. Synthetic isolated data only; real-model semantic quality remains manual acceptance. Creation uncertainty is preserved in the running store, not claimed durable across application restart. No version bump, packaging or remote release this round; dev.18ZIP remains unchanged.

Next verifiable slice B2 uses existing22h design: native independent behavior/dialogue example editor with explicit full-structure conversion, then shared write authority/CAS and workshop guarded publication/recovery. Read the relevant asset/editor/write tests before implementing; do not call B1 all of B. C world/preferences and M memory remain separate gates. A is completed history below.

## Completed slice — A messenger interaction acceptance

User authorizes development after22g discussion, and Astra design where necessary. Implement A only: compact conversation rows, left/right avatar bubbles, Enter/Shift+Enter/IME-safe keyboard, explained presentation cards, stream/key controls in current-session settings. Independent local UI preferences are scoped to browser origin and session, not LLM context or session schema; old dev.18 ZIP is not overwritten. Pure/helper and character browser checks passed; full old regression next, then source commit. B opening/examples is receiving an independent Astra engineering contract, no runtime implementation yet. C world/preference and M memory remain later gates.

A completed: Python500/500, Node76/76, visibility check,141-module build and complete Playwright/Edge32/32 (3.0m); wide/narrow screenshots inspected. Source delivery only, version and dev.18 package unchanged. Next gate B opening/examples must freeze author-source/ledger and edit-authority rules before implementation, not expand this UI slice into memory or world/preference changes.

A source commit3714a5b. Astra [22h](features/22h_character_opening_examples_b_contract.md) completed and read by main task; B1 optional opening atomic creation/frozen projection/ledger-source rejection is the next implementation slice, then B2 independent example editing with explicit conversion and guarded publication. No B runtime code yet. C/M remain separate gates. Do not silently treat a design document as feature completion or rewrite dev.18 ZIP.

## Latest user acceptance — design gate, not a new implementation round

User has opened dev.18 and supplied six character-chat UX/product comments. Record and discuss [22g](features/22g_character_chat_acceptance_design.md): messenger-style layout/keyboard/settings, explicit optional opening, editable behavior examples, worldbook triggering and preference projection. I1 remains complete. No runtime edits/version/package changes in this feedback round. Suggested next verifiable slice is P1 messenger interaction; opening/example data contracts follow, then world/preference integration, then the separate M memory gate. Proposed defaults are not silently treated as user approval.

## Current stage — I1 card semantics through a local portable package

Completed 2026-10-04: I1 implemented together with previous card-picker/world-binding/UX-S1 source changes. Final checks Python500/500, Node70/70, visibility, 138-module production build and complete Playwright/Edge31/31 (3.2m, includes workshop publication). Windows main EXE/updater compiled; dev.18 ZIP structure/version/privacy/overwrite-preserving-UserData passed, embedded modules and frontend hash verified. ZIP SHA25619fef8466d90b7bfc6b83126949222d5a30b09f0d4ee3427640e7bef9a0211b7. Old dev.17 package retained. No paid calls, player-directory changes, push/tag/remote release. Automated desktop launch remains unverified after the earlier policy rejection; hand off desktop/real-model acceptance to user. Stop here; subsequent M requires design and explicit scope confirmation.

User authorizes design followed directly by implementation, verification and Windows packaging. Final goal: external role cards have distinct persona/scenario/example semantics without modifying old conversations; deliver these changes together with UX-S1 in a local acceptance ZIP. First gate: freeze22f; then adapter/creation marker/projection and budget; then visible semantics/editor fallback; targeted and full regression; versioned local EXE/ZIP. No GitHub publication or paid model calls.

Story-memory reuse is being assessed and recorded, not substituted for the existing I1 mainline. Shared budget/complete-turn slicing/model routing can be reused; character knowledge/source/visibility and withdrawal invalidation require a distinct policy. No automatic character compaction, unlimited-memory claim or every-turn summarizer in this stage. Formal author openings, macros, inner worldbook activation, groupchat and personality evolution remain separate design gates.

## Latest slice — UX-S1 character sidebars

User authorized Astra design followed by implementation. [22e](features/22e_character_sidebar_and_card_semantics.md) freezes only UX-S1: searchable/pinnable conversation list with formal-reply previews and local unread watermark; current-conversation information, public experiences and settings; explicit private-record viewing with stale-request isolation. Source implementation is complete; acceptance is being recorded in TESTING. No conversation schema migration, extra LLM invocation, version bump, package overwrite or GitHub action.

Return to22d quality baseline and I1 card-field/opening design after this slice. Structured card semantics, formal imported opening and long-term memory remain design gates, not silently implemented. Existing dev.17 portable ZIP remains unchanged and lacks both the previous card-picker repair and UX-S1. Following current-slice statements are historical.

## Next-stage planning after packaged dev.17

Explicit user correction completed: character asset dropdowns replaced with a searchable shared card picker, optional worldbook binding directly exposed and bound world name visible. UI selection→provider context→reload verified; Node63, Python27 targeted, 135-module build and full browser29 passed. No runtime world replacement/schema migration/personality feature. Resume22d design gate; existingdev.17 archive is unchanged and does not include this source-only repair.

User asked to continue and distinguish existing design from new design. Current phase is the design gate in [22d](features/22d_character_next_stage.md): establish character-quality baseline, then freeze card semantics/compatibility (I1), then design sourced long-term memory. Do not implement groupchat/evolution or claim I1/long-memory fully designed. dev.17 package remains unchanged; desktop/real-model acceptance remains pending. This supersedes the following historical current-slice labels, not their completed evidence.

## Current mainline — minimal character conversation loop

### Latest verified status — dev.17 acceptance candidate

R1A/R1B/R2 playable core is complete: isolated sessions and frozen card snapshots, messenger/roleplay, sourced reversible local ledger, single-call streaming/non-streaming, stop/explicit retry/regenerate/undo, persisted recovery and per-session frontend ownership. Full check: Python 484/484, Node 63/63, visibility check and 134-module production build; Playwright/Edge 28/28 including six character scenarios. Wide/narrow screenshots inspected. Synthetic isolated providers only; real character quality remains user acceptance.

Final phase complete: actual Windows EXE + updater compiled and portable ZIP verified for version, private-data exclusion and overwrite preserving UserData. Actual EXE embedded archive includes all 11 character modules and excludes test modules. SHA256 d4aa66c6d34fcf366b5eb7f8ce1715958eb37509b430d4b28a3b66b1dc86e7a9. Automated desktop EXE launch command was rejected by local execution policy, so do not claim frozen-window smoke passed; user acceptance includes desktop launch and real-provider behavior. Version 1.6.0-dev.17 is user-approved; no GitHub publication. Hand off now and stop before new personality/groupchat/long-memory design. The following slice statements are chronological history, superseded by this status.

- User confirmed the minimal role-loading/one-to-one conversation first. Streaming is complete; resume bounded R1A→R1B→R2 in 22b. Long-term personality evolution defaults off and is deferred P2; core-extraction prompts/UI and real-time simulation are out of MVP scope.
- Current slice R1A-1: isolated character-session persistence and card snapshots, schema/path/size guards, atomic writes, revision conflicts and deletion tombstones. No model calls or empty character UI in this slice. Then lifecycle/API, single-response integration and streaming UI; storage tests are not evidence of a playable mode.
- R1A-1 is implemented: 11 new storage tests, complete backend 446/446 passed. Creation/profile snapshots, atomic persistence and CAS are present; action/ledger validation, pending recovery, HTTP routes, model integration and UI remain next. This is not all of R1A or the playable character mode.
- Product confirmations and retained future ideas are in 22c. Original card settings remain frozen; local knowledge/relationships/emotions may change. Future evolution can take effect with non-blocking notification, but no active evolution implementation now.
- User explicitly requested continuous implementation through a completed Windows EXE package, then user acceptance. Goal now includes the playable R1A/R1B/R2 loop, existing-regression and new-character browser acceptance, and a locally verified portable package. User approved version 1.6.0-dev.17; no GitHub push/release is implied. Parallel coding uses the previously authorized 6.1 Sol medium/high models. Data, API keys and generated test tooling are excluded from the distributed ZIP.

### Completed streaming and earlier design history

- User explicitly changed priority on 2026-10-03: finish streaming first. Pause the former R1A→R1B→R2 character implementation schedule; keep 22b as an engineering candidate, not proof of approved/completed character product design.
- Product modes are 故事—角色—工坊: story RPG, independent one-to-one chat roleplay, card authoring. Narrative-style character messages do not turn character mode into another RPG. Future in-story private chat is deferred.
- Phase goal: existing story normal/retry/reroll and all workshop chats, scope confirmed by the user. [23](features/23_streaming_story_and_workshop.md) defines bounded streaming integration without extra model calls or exposing JSON/state patches. Do not quietly build the entire character engine to deliver streaming.
- Product discussion and categorized ideas are in [22c](features/22c_character_product_vision.md): persona, sourced long-term memory, causally grounded change, typing status, future voice/images and adult intimacy roleplay. Core value/first-loop choices remain discussion, not implementation authority.
- Resume condition: streaming acceptance first, then discuss/freeze the character product MVP before resuming character code. Current F1/U1 evidence and prior engineering plans below remain history.
- Streaming stop gate reached: implementation and engineering acceptance complete (Python435, Node50, 130-module build, Playwright/Edge22). Exact boundary is in 23; no version bump/package/remote release. Do not expand into stop/replay infrastructure or character code merely because these tests passed.
- Next verifiable outcome is a discussed character product MVP: explain the core loop and value hypothesis in 22c, choose the initial behavior/memory/change scope with the user, then amend 22b if needed. Technical audit approval alone does not authorize inventing that product behavior.
- Character design continuation: optional authored mental cores and free-form persona are confirmed; user-controlled long-term personality evolution is confirmed. Defaults, approval policy, freeze semantics, relationship/ability boundaries and time simulation remain open in 22c. This is a documentation/discussion slice, not character implementation.

## Previous mainline — R0 engineering candidate (paused)

- Final goal: the first independently playable character private-chat loop, with saved conversations, character state, real streaming and safe retry/undo. Both messenger and roleplay presentation are user-confirmed session choices, sharing identity/history/ledger.
- Current phase: freeze and review [22b](features/22b_character_private_chat_r0_contract.md), not implement a full group-chat/NPC engine. The contract defines bounded storage, source-aware ledger operations, action/attempt identity, atomic persistence, cancellation races, streaming preview and reconnect status queries.
- Next verifiable slice: R1A storage/API/transaction tests without a real model; then R1B one-response request integration; then R2 streaming, session-owned frontend state and the reachable 游戏—角色—工坊 entry. User coding authorization applies to these reviewed slices; do not request a separate confirmation for each engineering milestone.
- Delivery: F1/U1 is already committed as `c396700`. This round changes design documents only; historical tests below are not new R0 implementation evidence. Version remains `1.6.0-dev.16`; no package, push or release. Bundling after R2 acceptance is a recommendation, not a confirmed packaging instruction.
- Deferred design gates: group chat, story NPC reuse, advanced external-card behaviors and world-rule revision history. Paid quality assessment and release authority remain separate from local engineering.

## Completed F1/U1 engineering evidence (2026-10-02)

- F1/U1 implemented and verified on 2026-10-02 within [22a](features/22a_first_slice_feedback_and_prompt_navigation.md): feedback uses one fresh snapshot per action, stale/unmounted results have no downstream effects, and manual sending remains explicit. Prompt modes preserve original registry order/permissions, guard dirty navigation and retain drafts on failures/authentication expiry.
- Current evidence: frontend Node 35/35; targeted feedback/prompt Python 34/34; `tools/run_checks.ps1` passed Python 412/412, visibility checks, Node 35/35 and production build (129 modules); complete Playwright/Edge 22/22 passed. Browser guards, override/restore, empty/read-only modes, expired-auth draft selection and feedback new-content/failure were exercised. No paid API or real Issue submission.
- Stop gate at that milestone: F1/U1 is complete, not a role engine or streaming implementation. Its next detailed R0 contract is now recorded in 22b. Reviewed F1/U1 changes are included in `c396700`; no version bump, package, push or release.

- User confirmed independent character conversations as a behavior research environment; navigation will be 游戏—角色—工坊. In-story private chat is deferred.
- User authorized 6.1 Sol medium/high coding after Astra freezes each design slice. [F1/U1 detailed contract](features/22a_first_slice_feedback_and_prompt_navigation.md) is implemented and verified. Remaining character/streaming design is separate from this completed slice; no paid model test or release action was authorized for it.
- Canonical brief: [feature 22](features/22_character_mode_and_state_design.md). User confirmed “链式输出” means streaming, not repeated generation. Existing external JSON/PNG import support is preserved; richer field/behavior compatibility remains staged.
- The former next slice (detailed R0 design) is now recorded in 22b above; do not treat completed F1/U1 as character-engine implementation.
- M1–M5 and W1a/W1b below are completed engineering history. Full world-rule revisions/committed-change undo and authoring UI remain deferred, not implemented by this change.
- Acceptance: current F1/U1 test results are recorded above and in 22a. Historical milestone counts below remain distinct evidence for those earlier slices.

## Completed implementation — W1; next step is the design gate

- Final goal: connect genre-neutral world-change signals, on-demand capture and source-turn/target-revision safety on the approved prompt architecture (feature 18). No scene evolution, asset extraction, new inbox UI or revision-history product in W1.
- Current slice W1a: a bounded `world_change_events` contract, independently registered short settlement instructions and generic detailed capture instructions; only confirmed events with an exact excerpt from the completed story may schedule capture. An explicitly empty/invalid/unconfirmed event list overrides legacy flags and command aliases.
- Compatibility: older custom model outputs without the new field keep the legacy boolean/explicit-command path. Existing add/update/retire proposals and review settings remain unchanged. New suspend/restore/expire signals do not grant unsupported historical restore operations.
- Acceptance: successful, attempted, reported and uncertain signals; scope/time enums and bounds; forged/missing evidence; empty events with a legacy true flag or genre alias; disabled feature prompt omission; valid signals reaching the detailed capture input; no extra request without evidence. Full Python/build/browser regression follows.
- W1a status: complete. Final Python regression 398/398, frontend behavior check, production build (126 modules), and full Playwright/Edge 22/22 passed. No paid model or player-data test was used.
- Next slice W1b: defer capture until story persistence succeeds, validate source-turn identity and target revision before publishing asynchronous results; include rerolls and undo races. This risk is recorded, not claimed fixed by W1a.
- Authorization: user asked to continue on 2026-09-24. No version bump, paid API requests, package or remote release.

### Completed goal-mode slice W1b (2026-09-25)

- User authorized continuous goal-mode work up to the existing Astra design boundary. Finish source-turn/revision-safe capture; stop before full immutable rule histories, new authoring UI or new automatic-publication policy.
- Queue capture inputs in the story runtime transaction; dispatch only after successful save. Failure restores the queue with the story checkpoint. Normal and reroll paths share this contract.
- The task pins its worldbook revision at dispatch and validates the persisted source using turn ID, player/story content and source message IDs. Reused numeric turn IDs after reroll are not sufficient identity. Validate again before commit under the story mutation gate; use an atomic expected-revision write for the target book.
- Do not hold the story gate during model calls. Other stories, edits and undo remain available; a stale result is discarded with a diagnostic instead of guessed merging. No new background repair/model request or persistent task retry queue.
- Validation: failed story save causes zero capture calls; valid source commits; undo/replacement during the model call rejects stale results; edits/deletions preserve the new target; failed writes preserve the old file; reroll queues its new source; full regression/build/browser checks.
- Boundary: this prevents an in-flight stale capture from committing. Reversing a worldbook change that already committed before undo requires the future rule-revision ledger and is not implemented here. Startup does not resume interrupted capture jobs.
- Evidence: Python 412/412, frontend behavior check and production build (126 modules), full Playwright/Edge 22/22 passed. The initial browser run caught an import-branch variable mistake; it was fixed and covered by an additional four-category API regression before the complete rerun passed.
- Stop condition reached: remaining product work requires freezing rule-revision storage and accepted-change undo semantics, authoring entry/inbox behavior and confirmation/publication policy. Do not begin those implementations merely because goal mode was enabled. No version bump, package, push or release was performed.

## Completed engineering stage — prompt architecture M1–M5

- Authorization: on 2026-09-24 the user enabled goal mode for the complete stage; M1–M5 may proceed without asking for a separate authorization at each milestone.
- Mainline: request composition, rule/data separation, finite experience presets, result contracts and request budgets/Overseer handoff are implemented. M1–M5 engineering acceptance is complete; release qualification remains separate.
- M5 implementation: connection-owned context/output limits; conservative estimated preflight at transport; raw and normalized usage/cache statistics; stable Overseer system rules with user data projections; proposed state and adjudication handoff; bounded content-free request observations and truthful developer coverage.
- Ownership: profile budget options persist with the existing connection repository and invalidate cached engines when changed. Runtime diagnostics retain 32 records in memory under a lock, expose no prompt/response body or credential, and are available through the existing protected developer endpoint.
- Budget policy: existing memory/retrieval owners retain responsibility for summarization and optional retrieval selection. Transport treats the retained assembled request as required, reports oversized sources, and rejects rather than silently truncating assets or commands. Unknown models use an explicitly labeled 32768-token conservative window, 4096 default output reservation and 10% estimate margin, configurable per connection.
- Acceptance: enforce zero provider calls on overflow; preserve output reserve; distinguish unavailable cache statistics from zero; stable Overseer rules; proposed state is visible to Overseer before live commit; disabled Overseer has zero calls; connection setting persists and cache reloads; UI distinguishes integrated read-only slices; full backend/build/browser regression.
- Quality boundary: deterministic acceptance proves request/state/UI behavior. Real-model literary comparison and provider cache effectiveness remain separate release-quality evidence; no claim of measured quality or cache-hit improvement is made from fake providers.
- Evidence (2026-09-24): `tools/run_checks.ps1` passed Python 389/389, frontend behavior verification and production build (126 modules); full Playwright/Edge passed 22/22. The browser checks exercise saved budget configuration and verify that Overseer receives current settlement state in user data, not entity data in static system rules.
- Delivery boundary: no paid API requests, version bump, package build, push or release in this stage closure. The current version label remains 1.6.0-dev.16; the new work is unreleased.
- Next after completion: resume W1 general world-change capture according to feature document 18. No further M-by-M user approval is required inside this stage.

## Completed unreleased patch — prompt architecture M4

- Final goal: implement the approved prompt architecture in bounded M1–M5 slices, then resume worldbook capture.
- Phase goal: make normal turns and rerolls share one strict settlement contract, calculate state changes on an isolated copy, and restore both memory and disk-visible state when a mutation cannot be committed.
- Implementation: model output is normalized before ledger/history/state mutation; malformed bars, Buffs, deletions and required influence reports reject the turn without guessing. StateManager plans on a copy and commits explicitly. Story API mutations keep a runtime checkpoint, save through same-directory atomic replacement, and restore the checkpoint if persistence fails. A failed reroll preserves the previously completed turn.
- Compatibility: existing settlement fields and the save schema remain unchanged. Unknown and duplicate influence reports are ignored with diagnostics, while a missing required triggered influence rejects the settlement. No repair-model call, universal patch schema, or additional story request was introduced.
- Status: implementation complete. Targeted M4 tests passed 33/33; the final one-command check passed Python 380/380, frontend behavior verification and a 126-module production build; Playwright/Edge passed 22/22. Documentation and the coherent Git commit close this slice.
- Known boundary: asynchronous worldbook capture and preference scheduling still require source-turn/revision validation in their owning later slices. Overseer budgeting and handoff order remain M5 work.
- Next verifiable slice after M4: M5 adds enforceable context budgets, normalized usage evidence, minimal Overseer projection, and prompt-workbench coverage. Do not resume worldbook capture inside M4 or M5.

The completed dev.16 node remains recorded below as historical evidence.

## Completed dev.16 patch — prompt architecture M3

- Final goal: implement the approved prompt architecture in bounded M1–M5 slices, then resume worldbook capture.
- Phase goal: M3 separates mandatory engine permissions from optional story-experience guidance, removes scenario-specific examples from always-on prompts, and exposes one finite advanced preset choice without creating an arbitrary prompt-import ecosystem.
- Implementation: player agency, causal continuity and the JSON/state contract remain mandatory. `AliveWorld default` adds only generic diversity and natural-progression guidance; `engine only` removes that experience slice from both future and settlement requests. Old saves and unknown values safely normalize to the default, and world-package recommendations can select the same setting.
- Prompt cleanup: police, guards, walkie-talkies, automatic alarms, ball lightning and prison-van examples no longer occupy the permanent engine prompt. Their underlying constraints are expressed as general permissions and causal rules and the concrete cases remain regression concepts.
- Status: complete. Targeted M3/world-package tests passed 67/67 before final versioning; full Python regression passed 366/366, the one-command frontend behavior/build check passed with 126 modules, and Playwright/Edge passed 22/22. Final versioned verification is recorded in the dev.16 changelog.
- Quality boundary: deterministic composition, settings, compatibility and UI behavior are verified. The paid 48-request real-model literary comparison was not run; it remains a pre-release quality check and this patch does not claim model-quality equivalence.
- Next verifiable slice: M4 centralizes result validation and transactional state application for normal and reroll paths. Do not resume worldbook capture or begin M5 budget/Overseer work inside M4.

The completed dev.15 node remains recorded below as historical evidence.

## Completed dev.15 patch — prompt architecture M2

- Final goal: implement the approved prompt architecture in bounded M1–M5 slices, then resume worldbook capture.
- Phase goal: M2 separates reusable instructions from request data in both future and settlement requests, registers explicit runtime projections, and keeps older developer templates that embed legacy variables usable without duplicate data.
- Implementation: default core prompts now contain rules only. Character/style/preferences/history are ordered before turn-scoped world retrieval, state, action and adjudication in the user message. Runtime prompt parts report their truthful feature/configuration/turn provenance, while normal and reroll settlement share one layout and retain their distinct trace labels and output limits.
- Compatibility: an active legacy core that still contains `{world_info}`, `{character_info}` or `{style_info}` renders those values in its original system location; the builder omits the corresponding user projection. No player save schema or model-call count changed.
- Status: complete. Targeted prompt/game tests passed 26/26; full Python regression passed 362/362; the one-command regression and 126-module frontend build passed; Playwright/Edge passed 22/22 after its asset-injection assertions were updated to inspect the new user data layer.
- Next verifiable slice: M3 removes duplicated experience rules behind a limited preset/on-off contract and proves disabled features contribute no rules, fields or data. Do not begin M4 result validation or resume worldbook capture inside M3.

The completed dev.14 node remains recorded below as historical evidence.

## Completed dev.14 patch — prompt architecture M1

- Final goal: implement the approved prompt architecture in bounded M1–M5 slices, then resume worldbook capture.
- Phase goal: M1 creates one pure settlement request builder and an observable request plan for normal turns and rerolls, without changing either path's wire text, generation settings or call count.
- Implementation: `core/story_prompt_builder.py` receives an explicit read-only snapshot; `core/prompt_studio.py` adds the system/user request plan and content-free user-segment manifest. Both callers keep their existing orchestration and error handling.
- Compatibility: normal settlement retains its length-sensitive output limit and runtime-slice order; reroll retains its fixed 3000-token limit and legacy order. The two known differences are now explicit rather than silently normalized.
- Status: complete. Targeted prompt/game tests passed 31/31; full Python regression passed 356/356; production frontend build passed with 126 modules; Playwright/Edge passed 22/22, including full asset-to-story injection, retry/undo, cross-story concurrency and developer prompt override/restore.
- Next verifiable slice after M1: M2 separates fixed rules from task data and registers explicit runtime projections while preserving legacy developer overrides. Do not begin M2 or worldbook capture inside the M1 commit.

The completed dev.13 node remains recorded below as historical evidence.

## Current dev.13 patch

- Final goal: extract the settlement state guidance and output contract into independently observable prompt slices without adding a model request or changing the rendered settlement prompt, then make the verified Windows package/release workflow reproducible.
- Phase 1: split `story.settlement.core`, `story.state.guidance`, and `story.state.contract` at stable contiguous boundaries; migrate any legacy full-core developer override atomically; lock composition equivalence and state-field coverage in tests.
- Phase 2: add an explicit release orchestrator that verifies version/changelog/worktree/tooling, runs automated checks, builds the portable ZIP, extracts only the matching changelog section, and creates a GitHub prerelease only when `-Publish` is supplied.
- Non-goals: no content-preset product UI, no prompt rewording/reordering, no additional LLM call, no real GitHub release in this development turn, and no state-data schema migration.
- Recovery: prompt overrides remain versioned in `UserData`; legacy full-core overrides are split before the first dev.13 read and the original text is represented by the three resulting records. Release failures leave local package artifacts for diagnosis and never modify `UserData`.
- Acceptance: exact rendered-prompt equivalence, required state-field regression, legacy override migration, release-script dry-run/preflight tests, Python suite, frontend build, complete Playwright suite, documentation, and a clean Git commit.
- Status: complete. Prompt/release targeted tests passed 23/23, Python regression passed 351/351, the production frontend build passed with 126 modules, and Playwright/Edge passed 22/22. The release preflight passed against a clean dev.13 commit, generated the exact version notes, and classified the channel as pre-release; no package or online Release was created.
- Historical next-slice proposal: return to worldbook capture. Superseded on 2026-09-15 by the prompt architecture design gate above.

The completed dev.12 node remains recorded below as historical evidence.

## Completed dev.12 patch

- Final goal: remove the remaining copy-button clutter, restore one reliable expanded editor for every ordinary multiline editing surface, and design—but do not yet implement—the next prompt architecture migration.
- Phase goal: ship the UI corrections with browser evidence; record the v1.5—v1.6 backlog and identify the next verifiable slice.
- Completion evidence: production frontend build, targeted Playwright assertions for special bubbles and expanded editing, documentation review, and a Git commit.
- Next verifiable slice after this patch: a read-only `PromptVariableRegistry` with searchable hover/click help, legacy aliases and composition-equivalence tests; then add layer/cache metadata before splitting the state-bar contract from `story.settlement.core`.
- Design record: [`features/20_prompt_layers_variable_registry_and_backlog_audit.md`](features/20_prompt_layers_variable_registry_and_backlog_audit.md).
- Status: complete. Canonical variables, legacy aliases, safe metadata API, searchable explanations, cursor insertion and prefix hashes are implemented without changing runtime prompt text or model-call count. Python regression passed 342/342, the production frontend build passed with 126 modules, and the complete Playwright/Edge suite passed 22/22.
- Next verifiable slice: design and lock byte-level equivalence fixtures for extracting `story.state.contract` and `story.state.guidance` from the settlement core; do not implement content presets or rearrange prompt order in the same slice.

The completed dev.11 release node remains recorded below as historical evidence.

## Mainline

Continue improving AliveWorld as a focused AI story game. Do not refactor it into an “everything is a plugin” agent platform. Preserve the existing domain-oriented architecture and repair the concrete ownership, persistence, concurrency, and interaction gaps exposed below.

## Final goal

Deliver one coherent, testable development node in which:

1. developers can inspect and safely override named prompt slices;
2. card assets return to the in-game right sidebar while world packages remain in the low-frequency resource library;
3. requests belonging to different stories or workshops can continue independently when the player switches views;
4. story, workshop, and log views open at their newest content without a visible top-to-bottom scroll;
5. story text is selectable without per-bubble copy clutter, while logs support selection, per-entry copy/export, and multi-entry export;
6. published workshop conversations remain available after restart without reopening an old published draft as editable state;
7. implementation notes and release notes are categorized by feature area;
8. another AI session can resume from repository evidence rather than the prior chat transcript.

The integrated node is versioned `1.6.0-dev.11`. On 2026-09-13 the user explicitly authorized a Windows portable build, GitHub push, and prerelease so it can be updated and tested.

## Architecture finding

The codebase is moderately well modularized, not “completely independent by file.” That phrase is neither true nor desirable: features must collaborate through stable contracts.

- Strong boundaries: backend domain modules under `core/`, route modules under `api/v1/`, frontend API modules, stores, and most components are separated by responsibility.
- Appropriate composition roots: `core/game_session.py`, `api/v1/game_routes.py`, and `aliveworld-ui/src/App.vue` coordinate cross-feature behavior.
- Current hotspots: `AssetPanel.vue` combines four asset domains and several workflows; prompt text is split between YAML and Python; `gameStore.js` and `workshopStore.js` each model only one foreground context; workshop publish/reopen semantics couple editable draft state to conversation visibility.
- Rule: split a hotspot only when the new boundary owns distinct state or behavior. Do not create one-file wrappers merely to claim independence.

## Prioritized slices

### Slice 0 — continuity and design gate (P0)

- Add this active-goal document and root handoff protocol.
- Create a reusable long-running software development Skill.
- Record ownership, lifecycle, concurrency, migration, and acceptance before code changes.
- Completion evidence: skill validation, documentation review, clean diff, Git commit.

### Slice 1 — navigation, scroll, and copy/export corrections (P1)

- Right sidebar exposes the four high-frequency card asset categories; resource library retains images and world packages.
- Story, workshop, and log containers set their initial scroll position to the bottom before presentation; subsequent auto-scroll occurs only when appropriate and never animates from the top on view entry.
- Remove copy buttons from ordinary player/AI story bubbles; keep selectable text.
- Logs are selectable and provide per-entry copy/export plus selection and batch export.
- Acceptance: frontend unit or component assertions where available, production build, Playwright flows for the restored navigation and each scroll/copy/export behavior.

### Slice 2 — workshop conversation history (P1)

- Editable workshop drafts and immutable published conversation history are separate concepts.
- Publish persists a history snapshot keyed by workshop ID, asset identity, type, scope/story ID, timestamps, and resulting revision. It contains conversation and safe operation summaries, never API keys or raw hidden credentials.
- Reopening an asset shows its latest history read-only and offers an explicit new/resumable draft path. Deleting the owning story follows existing story deletion; global asset history follows explicit asset lifecycle rules and is not silently discarded on publish.
- Existing resumable drafts migrate without data loss; old published files, if present, are indexed lazily.
- Acceptance: publish, restart, read history, start new draft, rename/delete lifecycle, and local/global scope tests.

### Slice 3 — prompt slice registry and protected editor (P1, prerequisite design already exists)

- Implement stable prompt IDs, default sources, ordered composition, override versions, token estimates, and a request-source manifest without increasing model calls.
- Developer mode requires a locally stored salted password hash and an expiring in-memory unlock token. It prevents accidental editing; it is not DRM or system-level encryption.
- Built-in prompts remain immutable. Edits create versioned user overrides with diff, restore, and validation. Ordinary players do not see developer controls.
- Initial migration covers the story/future/player-agency/continuity/world-change path before other prompt families; the UI must label unmigrated hard-coded prompts rather than imply full coverage.
- Acceptance: auth boundary, baseline/override/restore, composition equivalence, token/source manifest, restart persistence, and no-secret-log tests.

### Slice 4 — keyed background task concurrency (P1, highest implementation risk)

- Backend permits concurrent work across different story/workshop keys while serializing mutations of the same key.
- Frontend stores task state by stable story/workshop identity instead of one foreground `isProcessing`/`busy` flag. Results are committed to their origin context even after the player switches views.
- Story cards and workshop navigation show queued/running/completed/failed state. Returning to a context displays its current data without cancelling another context.
- Same-story turn submissions are queued or rejected deterministically; they never race writes. Closing/restarting the app leaves already committed data valid and reports interrupted ephemeral work honestly.
- No promise of parallel model throughput beyond the configured provider limits. Concurrency is bounded and respects task routing/rate limits.
- Acceptance: two-story overlap, story plus workshop overlap, same-story serialization, mid-request switching, failure isolation, reload recovery, and save integrity under fake-model and browser tests.

### Slice 5 — release integration (P1)

- Run the full Python suite, production frontend build, complete fake-service Playwright acceptance, and targeted Windows packaged smoke test if packaging is authorized.
- Update feature documents, roadmap, and both human-facing and technical categorized changelogs.
- Review version bump, package, GitHub push, and Release separately with the user.

## Non-goals

- No general plugin runtime or arbitrary generated Python/JavaScript execution.
- No conversion of AliveWorld into a general agent tool.
- No mobile redesign, community backend, Steam integration, or new model provider in this node.
- No simultaneous mutation of one story by multiple turns.
- No claim that a password-protected local editor is strong security.

## Progress ledger

| Slice | State | Evidence | Next action |
| --- | --- | --- | --- |
| 0 | Complete | Skill validator passed; repository protocol and goal committed as `64a0e4c` | Keep this ledger current after every slice |
| 1 | Complete | Frontend production build: 124 modules; Playwright/Edge: 17/17 passed | Commit navigation, scrolling, selection, copy and export changes |
| 2 | Complete | 327/327 Python tests; frontend build 124 modules; targeted Edge publish/reopen flow 2/2 passed; commit `458b1bc` | Preserve immutable workshop history contract |
| 3 | Complete | Prompt/auth/API/composition/trace 15/15; frontend build 126 modules; Edge override/restore 1/1 | Commit prompt studio slice |
| 4 | Complete | Keyed lock/session tests 3/3; frontend build 126 modules; deterministic concurrency Edge flows 6/6 | Commit keyed concurrency slice |
| 5 | Complete / release ready | Python 338/338; frontend build 126 modules; Playwright/Edge 22/22; portable verification passed; packaged health reports `1.6.0-dev.11` and `packaged=true` | Push development branch and main, tag and publish the authorized prerelease |

## Slice 1 implementation notes

- The resource library now owns images and world packages only. The right sidebar owns stories, worldbooks, characters, styles, entities, and local story settings.
- `useBottomAnchoredScroll` supplies immediate initial positioning and follow-only-when-near-bottom behavior. Story content additionally observes late image sizing so loaded images cannot leave the viewport above the newest message.
- Ordinary player/AI bubbles remain selectable and no longer display copy controls. Special diagnostic/future bubbles retain explicit copy affordances where their structured content is otherwise harder to select coherently.
- Logs remain local and already redacted by the backend. Per-entry and batch export serialize the currently returned safe log records in the browser; no export request uploads content.
- Playwright now prefers the repository virtual environment automatically, falling back to system Python only when it is absent.

## Slice 2 implementation notes

- Existing per-workshop JSON files are the durable source of both drafts and completed records. Published records are projected through `core/workshop_history.py`; no second copy of the same transcript is created.
- A published workshop is now terminal and read-only at both domain and API boundaries. “Continue” creates a distinct session against the latest formal asset, preventing an old published draft from silently becoming editable again.
- Reopening any supported asset returns all matching published conversations newest-first. The central workspace displays them as collapsible read-only rounds while keeping the current draft separate.
- History projection whitelists only role and content from player/assistant conversation messages. Internal/system records, drafts, model credentials, and request prompts are not exposed as chat history.

## Slice 3 implementation notes

- Built-in prompt sources remain in their owning YAML/Python modules. `PromptSlice` is a registry and composition boundary, not a second copy of every prompt.
- Only the six story future/settlement core, agency, and continuity slices are editable in the first migration. Dynamic length/preferences/suggestions and unmigrated world/workshop families are visible but read-only.
- Overrides are atomically saved under the portable user-data tree and selected at composition time. The old unprotected bulk YAML endpoint returns 410.
- Developer passwords use salted PBKDF2-SHA256 hashes. Unlock tokens are ephemeral and protect against accidental access, not users with filesystem/process control.
- Request traces record the ordered slice manifest and hashes so a defect can be tied to the actual composition without duplicating prompt bodies into metadata.

## Slice 4 implementation notes

- `core/session_manager.py` owns active-session identity and aggregate mutation guards. API route modules translate conflicts to HTTP 409; domain objects remain unaware of HTTP and frontend state.
- The frontend game store is a keyed context collection rather than a single foreground record. Story responses, failures, status bars, suggestions, last actions and draft input are committed by origin session.
- The workshop store uses the same keyed-context idea across all five workshop types while keeping domain-specific API adapters separate. Selecting another asset changes only the active key and does not discard the pending Promise or its context.
- Story settings autosave captures the originating session and an immutable payload snapshot. Save lifecycle operations share the story lock and retarget the session index after rename.
- Provider request limits remain governed by connection configuration. This slice guarantees application ownership and write integrity, not unlimited external throughput.
