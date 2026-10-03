# R0：独立角色私聊首个可玩闭环

> **当前实现覆盖（dev.17，2026-10-03）**：R1A/R1B/R2最简闭环已实现并验收。领域models/repository/contract/service、纯context/prompts、严格reply词法器与transport、独立HTTP/SSE路由、client API/store/Workspace分层；不是在故事引擎中塞角色逻辑。Python全量484/484、Node63/63、134模块构建、Playwright28/28（含6角色场景），宽/窄截图已检查。实际EXE打包为当前最后阶段，用户已明确授权本地dev.17，不授权GitHub发布。下文旧“未实现/未确认打包”属设计历史。
>
> 实现差异：慢消费者队列最多64项，满即取消，不等待原设计5秒；更严格且有界。single-process服务最多4个活跃生成，会话状态在启动时恢复中断，不在查询时误取消。源卡创建快照不自动同步，模型仅读取白名单和可见账本；单请求固定连接/模型/预算/提示词。默认trace仅记录元数据与省略标识，无私聊全文副本。
>
> 本地知识/信念/经历/关系条目具备来源和撤回逆操作；不是完整心理模型、自动总结或无限长记忆。近期上下文最多20回合，保护上限仍有效。长期性格演变及内核提炼没有开放入口。真实服务扮演质量留给玩家验收，不以假API工程通过替代。

> 2026-10-03最新确认：流式已完成，用户要求先实现最简角色载入/对话核心。恢复本文件R1A→R1B→R2必要闭环；演变和内核提炼均后置，不开放入口。角色卡快照冻结，局内记忆/关系/情绪可变化；时间仅来自聊天明确经过的时间。本轮先R1A-1存储/身份基础，后续API/生命周期与模型/UI不得据此标完成。本文旧“排期暂停”仅为历史。

> 2026-10-03 后续用户纠正：本文件仅为工程候选契约，不代表整个角色产品设计已完成或获批。角色代码排期暂停，先完成流式输出；完整产品讨论见[22c](22c_character_product_vision.md)。顶部产品名称是“故事—角色—工坊”，本文历史“游戏”称呼不应决定新UI名称。

日期：2026-10-03。设计基准：`c396700`，`1.6.0-dev.16`。状态：已通过主线程设计审阅的R0执行契约；尚无角色运行代码或本设计的运行验收。上级：[22](22_character_mode_and_state_design.md)；已完成的反馈/提示词导航：[22a](22a_first_slice_feedback_and_prompt_navigation.md)。

本文件冻结首版必要的可逆技术选择，供设计审阅后连续实施R1A→R1B→R2，不需要玩家逐个工程切片重新批准。群聊、故事NPC和高级外部格式仍有各自设计门。以下数字是首版保护上限，不是供应商能力或真实质量测量。

## 1. 玩家目标与范围

玩家从顶部「角色」选一个AI角色，直接以“我”或一张玩家卡开始私聊；会话能保存、切换、继续，回应逐步可见；中断、失败、重试、撤回不会留下错误经历或串到别的会话。

- 用户已确认首版同时提供「即时聊天」与「情景扮演」，由会话设置选择。`presentation_mode=messenger|roleplay`，两者共用身份、历史、账本和事务，不分叉为两套引擎。默认新建为messenger是可逆技术默认，不代表用户只要即时聊天；创建页明确可选两种。
- messenger偏对白，可含简短动作；roleplay可含场景/动作旁白，仍只决定AI角色行为，不替玩家新增对白、内心或决定。均返回同一`reply:string`，不要求模型另造气泡数组。旧消息保留生成时的模式标签；空闲时切换只影响后续输出，不重置人格或关系。
- 首版固定两个参与者：一个user、一个ai。玩家卡可空；AI卡必选。身份在创建时确定，开聊后不原地换人；换卡创建新会话。名称不是身份，旧`is_player`不决定新会话控制权。
- 流式属于首个可玩发行闭环P1，不能以R1B非流式后端已通宣称完整交付。明确不支持流式的兼容服务可选择非流式，完整成功后一次显示，不伪造打字流。
- 不含：群聊、故事内私聊、故事NPC接入、全员后台模拟、自动更新全局卡、自动总结模型、长期记忆引擎、分支树、批量迁移资产、卡内世界书自动导入、脚本/宏执行。首版无需这些才能开聊。
- 当前是否马上打包没有确认；建议角色可玩闭环一起进入下一打包评审，不将建议写成用户授权。本设计不改变版本、打包、push或发布。

## 2. 已核查复用边界

`core/ai_engine.py`使用同步OpenAI兼容SDK，`chat_json`有空白二次请求及宽松JSON处理；它不是现成流式通道。角色不能直接沿用空白重试/破损正文打捞作为成功。故事原调用、协议、测试保持不变。

复用`core/model_connections/{models,repository,runtime}.py`的连接/密钥/路由、`core/request_budget.py`的预算与usage、现有提示词注册/变量/manifest、`core/session_manager.py:mutation_guard`的命名空间锁、同目录临时写+fsync+replace的持久化模式。不复用`GameSession`为角色会话，不向故事settlement字段塞角色账本。

当前连接协议为openai_compatible/comfyui；新增文本任务路由`character`默认继承`story`，不复制API Key或创建独立设置中心。ComfyUI不能作为该任务连接；本轮不声称原生Anthropic/Gemini适配。角色请求快照固定解析后的连接/模型/预算/提示词修订，修改配置仅影响下一请求。

已有`core/external_formats/{adapters,png,service}.py`及导入API支持旧式/V2/V3角色JSON、PNG元数据、常见Lorebook单向导入及降级报告。首版直接使用已归一化角色描述与starting_scene；已有`_external_import.source`保留。拆分原始载荷到性格/示例等独立字段属I1，不阻断最小私聊，也不重写导入器。

## 3. 存储、身份及限额

唯一持久化所有者为角色会话仓储。目录为`PATHS.data_dir / character_sessions / {session_id}.json`（便携版是`UserData/data/character_sessions`），不放故事saves。文件名只由服务端UUID生成，API不接受磁盘路径。UUID统一规范字符串；日期为UTC ISO8601。字符串上限按Unicode码点校验，载荷上限按UTF-8字节，拒绝而非静默截断。

### 会话聚合v1

| 字段 | 类型/规则 |
| --- | --- |
| `schema_version` | 整数1；更高版本只读，不自动降级写回 |
| `session_id`、`title` | UUID；标题1–80字符 |
| `creation_fingerprint` | 创建参数规范化hash，重复创建比对此值，不比对后续修改过的标题/模式 |
| `revision` | 非负整数，仅成功领域变更递增；持久化请求状态不单独增领域revision |
| `created_at`、`updated_at` | UTC时间；不参与提示词缓存前缀 |
| `presentation_mode` | messenger或roleplay |
| `participants` | 恰好两个Participant，instance_id唯一，controller一user一ai |
| `world_binding` | null或一个只读创建快照：asset_ref、source_hash、snapshot；仅显式选择，不自动读卡内世界书 |
| `turns` | 正式完整回合，最多512；每轮两条Message，开场资料不冒充AI已说的话 |
| `ledger` | 有界条目，active最多128，总条目最多2048；含被supersede的可追溯旧条目 |
| `requests` | Action及Attempt记录；最多2048个action、4096个attempt；幂等索引可由数组派生 |
| `extensions` | 命名空间对象，首版不执行/不注入；深度≤8，合计≤32KiB |

整个会话文件≤32MiB，写入前检查候选文件大小。达到回合/记录/文件上限返回明确只读可继续查看的状态，建议新建会话；不丢原文、不偷偷删幂等记录、不自动续费总结。首版不承诺无限长聊天；扩容/归档是后续独立切片。

Participant：`instance_id:UUID, controller:user|ai, display_name:1..80, asset_ref:null|{kind:'character',key:string}, source_hash:null|string, profile_snapshot:object`。snapshot完整复制原内部资产（每份≤8MiB，深度≤32），未知扩展原样保留但不执行。原卡无稳定ID时key仅作创建时来源定位，内容hash作修订证据，不反向依赖可变名称。user无卡时snapshot为`{name:'我',description:''}`；AI必须有非空描述。模型投影只读白名单name/description/starting_scene，不包含is_player、文件路径、原始外部扩展或凭据。name≤80、description≤32000、starting_scene≤8000；超限给字段提示，不能截断后暗称完整导入。完整快照限额与模型投影限额分别检查。

可选world_binding复用现有归一化世界书读取，快照≤8MiB；R1A仅保存，R1B使用显式公开常驻规则+有界相关条目投影，不调用捕获、不修改源书。首版不提供“隐藏于当前AI但由全知后台读取”的世界设定；选择页说明载入的公开规则会提供给本AI，卡内世界书仍不自动绑定。复杂触发行为不通过复制快照获得等价支持。

Message：`message_id:UUID, turn_id:UUID, speaker_instance_id:UUID, content:1..8000, presentation_mode, visibility:{audience_instance_ids:[UUID,UUID]}, created_at`。user输入≤4000；reply≤8000。只存最终文本，不存逐字预览/内部reasoning。新建/发送JSON请求≤64KiB（资产以引用选择，不上传大快照）。

Turn：`turn_id, action_id, request_id, user_message, ai_message, mode_at_generation, ledger_inverse, committed_revision, created_at`。`ledger_inverse`仅记录本轮新增entry_id与本轮被改变条目的前值，不复制整卡/整本历史；只有经过验证的小操作能生成逆操作。被撤回或替换的回合从正式turns移到**生成该回合的原action**的`archived_turn`（同一结构，每个生成action最多一份），保留本地恢复输入与审计，但不投影给模型。一次action最多成功生成一轮，因此后续撤回/重生成不会覆盖它已归档的结果；undo action不再复制归档。不提供自动复活旧回答或分支合并。

### 局内账本

Entry：`entry_id, subject_instance_id, kind, content, about_instance_id?, source, visibility, status, supersedes_entry_id?, created_turn_id`。

- kind为knowledge/belief/experience/intent/relationship；content 1–400字符。稳定人格/边界仍在只读profile，当前目标可作intent；不新增强制心理量表。relationship必须有本会话about_instance_id且不能等于主体。
- source为`{type, message_ids, evidence}`：type为author/player_statement/dialogue_event/model_inference；message_ids 1–2个（author可空）；evidence≤2个`{message_id,quote}`，quote 1–240字符，必须逐字属于所引正式文本或本轮待提交文本。模型不得选择author；author只可由创建资料的确定性投影产生，首版不提供任意作者事实编辑器。
- source表示依据，不证明自然语言真实。玩家陈述可支持“对方说过X”，不能直接证明X客观发生；model_inference只允许belief/intent/relationship。experience只能记录本轮对话中确实表达/完成的交互，不能凭模型杜撰外部经历。knowledge只能是明确标注的“收到的信息/已知公开资料”，不得将对方声称升级为无来源世界事实。
- visibility使用明确`audience_instance_ids`，首版仅允许两人公开或AI自己；subject只能是当前AI，不能模型修改玩家知识/意愿。每条source的可见范围必须覆盖主体；账本对外披露不能超出其来源可见范围。模型不能扩大既有条目的可见范围。
- status为active/superseded，旧条目不覆盖掉来源；supersede必须同主体/同kind/同about，目标为当前active且本次投影已提供的条目。不允许模型删除、恢复、跨会话引用或任意路径patch。
- “AI自己可见”是角色世界的知情边界，不是对电脑所有者的安全隔离。默认右侧只展示双方公开账本；显式“查看角色内部状态（剧透）”可查看结构化条目和来源，不输出内部思维链。浏览器普通会话响应不夹带未请求的私有账本。

可见性过滤在检索/相关性排序之前完成。请求仅包含当前AI有权看到的消息和条目；未来群聊可复用ID与audience，不在首版发明权限平台。

## 4. 单次模型结果与上下文

角色任务标识`character.reply`；独立登记`character.reply.core`（职责/权限）、`character.reply.contract`（只读契约）、`character.reply.presentation`（当前模式），动态资料来自纯builder。只有R1B实际接入后才在既有角色提示词tab呈现为已接入；不得改故事prompt IDs或其输出契约。

输入两消息保持现有兼容路径：system固定职责+契约+有限表现指引；user为参与者白名单快照、公开世界投影、可见账本、近期完整回合、当前user输入。角色任务变量单独注册，manifest记录来源ID/hash/预算，不复制私聊正文。外部卡内容是资料，不能执行其中工具/脚本或覆盖代码校验。

工作窗口：最近20个完整正式回合；active账本先可见性过滤，再按当前文本词匹配、更新回合、新ID稳定排序，最多32条；意图最多保留8条参与候选。被省略历史与条目ID/计数进入诊断，不改原文，UI说明“使用近期对话和局内记录，非完整长期记忆”。profile、必需规则、当前输入及最近2回合为必需集合；可选世界检索/其余旧回合/其余账本按完整条目移除至预算可容纳。必需集合超限零供应商调用，返回CONTEXT_LIMIT；不得截断JSON/文本中段。无需每轮第二次提取/总结调用。

输出严格顶层对象，仅允许以下字段；无Markdown围栏、前后解释或重复key：

```json
{"reply":"本轮可见回复","ledger_ops":[]}
```

`ledger_ops`必填数组，最多6项，空数组为不变。操作只有：

```text
add      {op, kind, content, about_instance_id?, source, visibility}
supersede{op, target_entry_id, kind, content, about_instance_id?, source, visibility}
```

模型不生成entry_id/turn_id/subject/controller/revision，均由代码绑定。新增source只允许当前user候选消息、当前reply候选消息或本次请求实际提供的正式可见消息，不能引用未提供的旧消息ID；message ID在发请求前分配，未完成不成为正式消息。同一target不得操作两次；所有操作先独立验证并在副本应用，再整轮提交。一项非法则整轮失败，不选择性偷偷丢patch而保存reply。最终原始输出≤64KiB、深度≤12；重复key、未知字段、非有限值、工具调用、多个choice、空reply或非正常终止均失败；不补JSON、不“打捞成功”、不自动修复AI调用。

代码能验证身份、权限、来源引文、类型与事务，不能证明每句内容符合人格或判断经历真假。语义质量另评测，不能把schema通过等同角色可信。

## 5. Action、Attempt、原子事务

客户端对每次玩家意图生成`client_action_id:UUID`（action_id），服务端对每次显式生成分配`request_id:UUID`（attempt）。Action保存`action_id, operation:send|regenerate|undo, fingerprint, created_at, attempts, target_turn_id?, result_turn_id?, result_state:active|withdrawn|replaced|null, archived_turn?`。Attempt保存`request_id, retry_of?, retry_token?, base_revision, status, error_code?, committed_revision?, created_at, ended_at?, pending_input?`；status为pending/committed/failed/cancelled/interrupted。pending_input只保存操作所需user文本/候选消息ID及模式，不属于历史、不参与其他请求，终态清除（失败输入可在action中保留一份供显式重试，UI标未发送）。undo是零模型立即事务，也记录action/committed attempt以保证重复点击幂等。凭据、assembled prompt和流式残片不入聚合。

Attempt.status记录执行是否成功，提交后永远为committed，即使回合后来被撤回。Action.result_state记录生成回合的当前位置：send/regenerate成功为active，被undo为withdrawn，被后续regenerate为replaced；尚未成功生成和undo操作自身为null。undo仅记录target_turn_id，不产生result_turn_id。查询同时返回两者，不能见旧committed就恢复归档气泡。例如A生成T1→B重生成T2→C重生成T3：T1归档到A、A=replaced；T2归档到B、B=replaced；T3正式属于C、C=active。再撤回T3只归档到C并设C=withdrawn，A/B归档不变。全部归档计入会话32MiB上限，不会无限覆盖同一槽位。

fingerprint由规范化操作、输入、模式和目标回合计算，排除retry请求的expected_revision；相同action_id不同fingerprint返回IDEMPOTENCY_MISMATCH，不“最后写覆盖”。相同action重复POST只返回已有状态/结果，绝不新增模型调用。retry使用原action_id与新的retry_token（客户端UUID），指定retry_of；同retry_token重复也幂等。已提交、已撤回的action都不能通过retry复活；只能新建玩家意图。请求记录在会话生命周期内不静默过期。

单会话一个pending；短锁使用`mutation_guard('character', session_id)`。模型网络等待不持锁，不用故事/全局锁；不同会话与故事/工坊可并行，受原连接限制及角色在途上限约束。首版角色全局在途上限4，超过返回429，不排隐藏自动付费队列。

1. 短锁中加载权威文件，验证schema/revision/幂等/容量、空闲与输入，建立不可变输入快照；原子写pending记录。写失败不调用模型。仅请求状态变更不递增领域revision。
2. 释放锁，组装/预算后执行至多一次供应商请求。输出只写内存预览；pending记录并不是发送成功。
3. 完整JSON校验，在隔离副本生成两条消息、账本变更与inverse。
4. 再取同锁，确认本attempt仍pending、base_revision匹配、会话仍存在；原子替换会话文件，提交turn+ledger+committed请求记录，revision+1。只有replace成功后刷新内存并发committed。
5. 同目录临时文件、flush/fsync、os.replace；写前/replace故障保留旧文件、清临时文件。不得先更新内存或逐条写消息/账本。replace成功但响应丢失，用状态查询识别已提交；不将其重新调用。部署限现有单进程服务，不支持多个worker同时写同一UserData，实施启动配置需明确拒绝该模式，不为此建设分布式锁。

失败终态也需原子写。终态写失败则内存封锁该会话写操作，返回PERSISTENCE_FAILED，提示重启恢复；不能将仍为pending的磁盘状态误报为已取消。服务重启首次加载把所有pending原子改interrupted后才允许写；失败则只读。无自动任务恢复/请求重放。文件损坏保留原件只读报错，不自动当空会话覆盖。

取消与commit由同一锁线性化：cancel先落盘→任何迟到输出不得commit；commit先落盘→cancel返回already_committed和revision。取消尽力关闭供应商流/HTTP等待，不能保证供应商立即停止计费。终态cancel成功即允许下一轮；旧任务由request_id永远隔离，连接关闭仍在后台清理但不会释放别人的pending。

### 撤回与重新生成

- “撤回最后一轮”只对当前末尾正式turn开放，空闲+expected_revision；原子移出两条消息、重放ledger_inverse、把回合保存到其生成action的archived_turn、设原action.result_state=withdrawn，本次undo attempt置committed，revision+1。不改profile和世界快照，不逆转全局资产（本就未写）。输入回填草稿不自动发送。可以连续撤回末尾；每次独立意图ID和revision。
- “重新生成最后回复”是新regenerate action，指向当前末尾turn；模型使用其前态账本+前缀历史+原user输入，旧完整回合继续有效并显示“正在重新生成”。成功一次原子替换末尾回合/账本并保存被替换旧回合；失败/取消保留原回合原状态，不能先撤回再调模型。生成时模式采用当前会话设置并标记新消息，用户输入不偷偷改写。首版不提供编辑历史中段。
- “重试失败请求”只对failed/cancelled/interrupted，显式点击才新attempt；验证当前revision等于失败尝试base_revision，否则STALE_RETRY，提示以当前状态作为新发送。网络状态未知先查询，不直接重试。
- 正在生成时禁标题/模式/身份/绑定修改、撤回、regenerate、删除；返回SESSION_BUSY而非排队。删除需确认、空闲、expected_revision；在原路径原子替换为无内容最小墓碑`{schema_version:1,session_id,deleted:true}`，清除标题/参与者/正文/账本/快照/请求等全部会话数据，不删源卡/源书/其他会话。墓碑不进入列表，仅防旧创建请求重放，不新增服务或数据库；随本地数据目录保留，不自动过期。用户手动清除该数据目录后不承诺识别旧ID。取消确认终态后再删。

## 6. API契约

路由前缀`/api/v1/character-sessions`。保留既有本地应用访问边界；不新增远程公开服务。所有mutation限制JSON字段与ID，expected_revision不接受省略；创建除外。普通响应仅含可展示投影，不直接把聚合文件返回浏览器。

| 方法/路径 | 输入/结果 |
| --- | --- |
| GET `/` | 分页列表limit≤50、cursor；title/参与者名/模式/revision/运行状态，不含正文 |
| POST `/` | client_creation_id、title?、ai_asset_ref、user_asset_ref?、world_asset_ref?、presentation_mode；201返回会话投影。服务端用固定应用namespace+client_creation_id派生UUID为session_id，重复同creation_fingerprint返回原会话，冲突409；命中删除墓碑返回410 SESSION_DELETED，不复活。新建必须新creation ID；墓碑检查先于资产读取/模型访问 |
| GET `/{id}` | 会话元信息、最近20回合、公开账本、pending状态；无临时输出 |
| GET `/{id}/turns?before=...&limit=...` | 正式历史分页，limit≤50；不返回withdrawn或内部状态 |
| GET `/{id}/ledger?view=public|spoiler` | 显式剧透查看，仍是结构化条目非推理链 |
| PATCH `/{id}` | expected_revision、title?/presentation_mode?；空闲时原子更新revision+1，不重写历史 |
| POST `/{id}/actions` | client_action_id、expected_revision、operation、content或target_turn_id、delivery=stream|non_stream；undo立即200；生成提供同一终态语义 |
| GET `/{id}/actions/{action_id}` | action与当前/指定attempt终态、result_turn_id、revision、安全错误；不存在404，不推断已发送 |
| POST `/{id}/actions/{action_id}/retry` | expected_revision、retry_of、retry_token、delivery；重新验证后新attempt |
| POST `/{id}/requests/{request_id}/cancel` | 幂等取消；同锁返回cancelled/already_committed/已有终态；无需expected_revision，以具体request_id线性化 |
| DELETE `/{id}` | expected_revision，空闲时原子替换最小墓碑，204；已是墓碑时重复删除204，不再访问模型。其他针对墓碑的读写均410 SESSION_DELETED |

生成non_stream保持连接等待最终JSON `{session_id,action_id,request_id,status,revision,turn?}`；stream为fetch POST读取SSE（不用仅支持GET的EventSource）。重复已存在pending action不另附一个拥有取消权的流，返回202 JSON状态；客户端保留原流或查询。不支持无界事件重放，查询返回持久终态即可。

错误统一`{error:{code,message,retryable},session_id?,action_id?,request_id?,revision?}`；message为安全本地说明，不回传供应商URL、认证头、整段raw异常或prompt。

| HTTP/code | 处理 |
| --- | --- |
| 400 INVALID_REQUEST / 422 CONTRACT_INVALID | 玩家字段错误/模型最终结构错误；后者为attempt failed |
| 404 SESSION_NOT_FOUND / ACTION_NOT_FOUND | 重新加载列表或查询；零自动模型调用 |
| 410 SESSION_DELETED | 已删除，旧创建/发送请求不能恢复；新建需要新creation ID |
| 409 REVISION_CONFLICT / SESSION_BUSY / IDEMPOTENCY_MISMATCH / STALE_RETRY | 保留草稿，刷新权威状态；不得自动合并重发 |
| 409 SCHEMA_READ_ONLY / 413 SESSION_LIMIT / INPUT_LIMIT | 查看仍可用；明确升级或新会话/缩小资料路径 |
| 422 CONTEXT_LIMIT / CONNECTION_UNSUPPORTED | 发送前拒绝，提供安全来源占用/连接选择提示 |
| 429 CAPACITY_LIMIT / PROVIDER_RATE_LIMIT | 不排自动重试；显式稍后再试 |
| 502 PROVIDER_FAILED / STREAM_UNSUPPORTED / PROVIDER_TRUNCATED | 保留原历史；可选择非流式作新显式attempt |
| 504 PROVIDER_TIMEOUT | 中断待提交请求，不把残片入库 |
| 500 PERSISTENCE_FAILED / SESSION_CORRUPT | 不报成功；会话只读/恢复提示，无自动覆盖 |

SSE响应头发送后无法再变HTTP状态，统一`failed`终态携带上述code，随后关闭。取消是cancelled终态，不用伪造模型错误。

## 7. 流式、解析与连接降级

### 最小传输适配

在AIEngine新增独立角色raw completion方法/薄transport边界，保持`chat_json/chat_text`旧默认行为。角色方法复用配置、budget、usage和安全trace，显式`max_retries=0`（SDK与应用两层），stream/non_stream均一次调用。可在角色transport内使用同SDK的异步客户端以便取消HTTP等待，不把同步生成器直接阻塞FastAPI事件循环；不为了角色把全部故事调用改async。依赖版本以仓库锁定环境检查为准，实施时用隔离假兼容服务验证SDK流结构，不凭接口名称声称供应商支持。

能力矩阵：openai_compatible且已验证stream→真实stream；已配置non_stream→一次非流式；未知默认尝试stream但失败后明确提示选择non_stream；ComfyUI/原生非兼容协议→发送前拒绝。模式仅为`character`任务的delivery设置/请求参数，不增加万能供应商能力数据库。response_format=json_object沿用当前兼容目标；不支持该参数的服务本阶段明确不兼容，不能偷偷去掉契约或二次发送。

流式已开始后无自动回退、无自动补请求；请求头拒绝stream也不默认无费用，均由用户明确重试non_stream。关闭usage扩展参数以保持兼容；如果chunk自带usage才归一化，无则null，不为统计再请求模型。不展示reasoning_content、tool_calls或除choice[0].delta.content外的字段。

现有`begin_llm_trace`/`finish_llm_trace`接收完整prompt/response，角色不能直接照抄调用。使用内容最小化包装层，仅传任务/ID/manifest hash/预算/usage/耗时/安全错误码；prompt、response、raw异常正文均不得进入默认trace或logger。底层若要求文本，传固定省略标记，不传原文，保持旧故事默认不变。首版不新增私聊原文日志开关，后续内容调试采集另设计授权/脱敏/保留期限。测试用独特合成正文断言默认日志和请求诊断均不含正文、卡片内容与密钥，不只检查浏览器响应。

### SSE事件v1

每个事件含`v:1, session_id, action_id, request_id, seq`；seq从1单调增加，客户端对每个request去重，旧request事件不覆盖当前预览。事件data是JSON，正文经标准序列化，不能拼接未转义换行到SSE帧。

| event | data增量字段/语义 |
| --- | --- |
| accepted | base_revision、delivery；pending已落盘但无正式消息 |
| reply_delta | text：只包含完整解码的reply字符，≤2048字符/事件 |
| validating | 停止预览追加，尚未提交 |
| committed | revision、turn_id、最终两条Message和公开账本投影；替换临时预览，以落盘文本为准 |
| cancelled | code=USER_CANCELLED或CLIENT_DISCONNECTED、revision |
| failed | code、安全message、retryable、revision |

每15秒发送无内容heartbeat SSE注释，不增加seq。仅临时状态机accepted→streaming→validating→committed或cancelled/failed；无reply_delta时也允许进入validating。客户端收到committed后关闭；EOF无终态一律“状态待确认”，GET action查询后才显示成功/失败。GET获pending时可每2秒查询，最多到服务端总超时+10秒；之后显示连接不可达而非猜失败。页面重载按会话pending信息恢复查询，不自动模型调用。

### JSON增量解析器

使用小型、有界、单次扫描的JSON词法/结构状态机（领域私有，不建设通用流处理平台），与最终严格JSON解析独立。跟踪对象/数组栈、键/值位置、字符串/escape、`\\uXXXX`和代理对、顶层已见key；只在根对象的`reply`值为字符串时释放字符。未知字段/重复key可立即中止；字段顺序允许任意，但提示词要求reply先输出，以减少首字延迟。不能用正则、找到第一个引号、拼尾部括号或每chunk重新解析全部累计内容。

SDK返回的content已是字符流；网络SSE解码由SDK处理。浏览器对服务端字节用TextDecoder(stream=true)+SSE分帧，正确处理UTF-8字符跨字节、CRLF、分段data；服务端JSON词法仍覆盖转义跨chunk和代理对，非法/孤立代理不释放。保留≤64KiB原始JSON作最终独立解析；最终拒绝重复key、尾随垃圾、深度/长度溢出并执行§4领域验证，即使预览看似完整也不能绕过。

保护默认：首响应/无内容空闲超时60秒、请求总时限180秒（包括reasoning导致的等待），原始响应64KiB，最大事件10000；客户端单事件buffer≤256KiB、整个预览≤8000字符。心跳不刷新供应商内容超时。流消费者队列≤64事件，慢消费者超过5秒无法排空则取消而非无界缓存；正文delta可合并到每50ms一批，但不伪造内容。限额集中常量，测试虚拟时间，不在普通设置堆滑块。

真实网络断开/浏览器关闭默认cancel未完成请求；服务端监听连接断开并执行相同取消入口；显式stop先发cancel再关闭本地流，若cancel请求也失败则状态待确认。游戏↔角色↔工坊、角色A↔B切换只是视图变化，store继续消费流，不是网络断开，不应调用abort。首版无detach后台付费任务或可重连事件日志；短暂断线也不承诺续流，已commit则查询找回，未commit则取消/超时。

## 8. 文件边界与最短UI

| 层/建议文件 | 唯一职责 |
| --- | --- |
| `core/character_chat/models.py`、`contract.py` | schema/限额/权限、纯操作校验和inverse；不依赖FastAPI/Vue |
| `core/character_chat/repository.py` | 聚合读写、版本只读、原子文件、pending重启恢复；复用实际原子写机制，不动故事格式 |
| `core/character_chat/service.py` | action/attempt生命周期与短锁、取消/重试/撤回；不写prompt字符串或HTTP响应 |
| `core/character_chat/context.py`、`prompts.py` | 可见投影与有界上下文、纯ModelRequestPlan；不写数据文件 |
| `core/character_chat/stream_json.py` | 有界词法提取reply及解析测试；不提交状态 |
| `core/ai_engine.py`或紧邻transport模块 | 新角色单次raw/stream调用、预算、取消与usage；保留旧故事默认行为 |
| `api/v1/character_chat_routes.py` | 请求DTO、安全错误、SSE映射、断线转cancel；注册处只include_router |
| `aliveworld-ui/src/api/characterChatApi.js` | fetch/SSE解码、安全错误与状态查询，不掌管活动会话 |
| `aliveworld-ui/src/store/characterChatStore.js` | 按session_id/request_id隔离上下文、draft、inflight、preview、终态恢复；组件卸载不停止流 |
| `aliveworld-ui/src/components/character/CharacterWorkspace.vue`及局部子组件 | 列表/创建、消息、输入/stop/retry、公开状态与显式剧透；不复制领域校验规则为新权威 |
| `TopNav.vue`、`App.vue`、`uiStore.js` | 增加character枚举与明确三个视图分支；不在壳层塞领域代码 |

可因实际代码耦合合并小文件，但责任不能倒置；不先抽通用聊天平台。gameStore、workshopStore沿用既有按源会话归属，不销毁其任务。角色store生命周期为应用而非Workspace；UI可卸载，draft/Promise/reader仍由store持有。

最短路径：角色→新对话→选AI卡（必选）→默认“我”与即时聊天，可展开选择玩家卡/情景扮演/公开世界书→开始→输入→发送。无卡引导去现有角色工坊/导入后返回，不强迫心理字段表单。已有starting_scene显示“角色场景资料”可折叠，不直接当AI开场白入历史；导入first_mes的独立恢复后置I1。

左栏会话名、模式、运行标记；中栏正式历史与醒目标注“生成中/未保存”的临时气泡；输入草稿在每会话store中保留，失败不丢。右栏参与者只读快照、公开局内条目及来源、会话模式设置。AI生成期间其他会话仍可操作；发送当前会话禁重复，stop保持可用。临时气泡取消/失败后从聊天流移除，失败卡可保留输入与安全错误，不复制成正式助手消息。重载/断线查询期间禁重复发送直至明确状态。当前TopNav模式按钮在md以下隐藏，R2必须增加小屏可达的紧凑模式入口并验证三种模式都能进入，不借此全面重做移动端。

每条正式消息保留mode标签，渲染Markdown走已有安全策略，禁止外部HTML执行；未知卡链接不得自动访问。会话删除二次确认明确“仅删除此对话与局内记录，不删除角色卡；保留无内容删除ID防旧请求恢复”。首版不增加原始prompt浏览器入口，日志不得新增私聊raw文本的默认持久副本，严格使用§7内容最小化包装层。

## 9. 兼容与迁移

- 新schema只用于新目录；旧角色卡、旧故事is_player与存档完全保留原读取路径。不删除旧开关、不批量改写旧卡、不从多个旧player中静默任选。玩家在新建私聊明确选择谁由AI/自己扮演。
- 创建快照后源卡改名、编辑、删除都不影响本会话；再次选同卡创建另一个instance。未做全局ID迁移前source key只是来源描述，不自动追踪“最新卡”。资产删除无需扫描并重写所有私聊。
- 当前v1无旧角色会话待迁移；以后迁移先备份到同目录独立bak、验证新候选再replace，失败保原件、幂等版本门。未知更高schema只读；不能用默认v1清空未知内容后写回。
- 外部I0回归保留导入预览、PNG解码、原始字段及降级报告。I1字段拆分/P2高级宏和触发仍独立验收。首版不能把读取description说成酒馆行为等价。

## 10. 实施依赖与完成证据

### R1A-1真实实现（2026-10-03）

- `core/character_chat/models.py`：创建身份/快照、双控制者、双表现、只读模型资料投影及限额；`repository.py`：UUID路径、原子写入、修订CAS、创建幂等、冻结原卡快照、删除墓碑、未来schema只读保留。
- 单进程每会话存储锁使用既有mutation_guard，模型生命周期锁/API接入尚未实现。仓储只检查聚合外壳；turn/ledger/actions的完整业务校验、pending恢复与生成期间禁止删除归下一切片。不能将内部仓储方法直接作为未验证HTTP入口。
- 11项专项测试及全部后端446/446通过，仅临时目录与合成数据。没有真实API调用、玩家数据访问、角色UI或打包发行。旧435项全部保留；此处不是R1A全部或R0可玩验收。
- 下一片：完整领域动作/账本与恢复语义、资产解析及创建/查询API，再单次模型与流式UI。局内情绪细化可以针对实际对话质量升级，不先建复杂心理表格。

| 切片 | 前置/交付 | 必须验证/停门 |
| --- | --- | --- |
| R0设计 | 本契约审阅；双表现模式已由用户确认 | schema/API/事务/流式/文件责任无互相矛盾；文档不是实现证据 |
| R1A数据/API（P1） | 依赖R0；聚合仓储、创建/列表/读/模式设置/删除、纯ledger与undo计划、请求状态机；生成服务注入fake transport只在测试存在 | UUID/来源/可见性/限额/未知schema；原子写故障；重启pending恢复；幂等/取消竞态；旧卡/旧故事文件字节不变；发行API在LLM未接入时明确不可用，不放可发送空UI |
| R1B单轮非流式（P1） | 依赖R1A；character路由、真实单次transport、builder/预算、完整结果提交、失败重试/末轮regenerate/撤回 | 假兼容HTTP服务检查真实请求和调用数；profile+模式投影、账本来源、超预算零调用；坏JSON/partial/写盘失败零半提交；重载、双会话归属；独立prompt切片真实接入。仍非完整发行闭环 |
| R2流式+双模式UI（P1） | 依赖R1B；SSE/JSON词法、取消断线、三入口、store及公开账本UI、显式非流式设置 | chunk边界全枚举/随机切分（引号、反斜杠、中文、emoji代理对、嵌套reply假键、重复key、垃圾后缀）；真实浏览器逐步预览、失败移除、取消/commit竞态、模式/会话切换持续完成、刷新终态恢复；原game/workshop并行回归 |
| 首发行候选评审 | R2工程通过+模型质量取样+无P0/P1 | 再决定版本/包/发布；不因本契约自动执行付费或发行 |

R1A→R1B→R2每片独立提交证据与文档，由主线程审阅；不要求用户批准每个M式技术步骤。实现若暴露必须改产品/隐私/费用行为的选择才回设计门，普通可逆文件拆分自行决定。达到上述MVP且无P0/P1后不继续扩展群聊/I1大改，返回发行评审。

确定性专项建议`tests/test_character_chat_contract.py`、`test_character_chat_repository.py`、`test_character_chat_lifecycle.py`、`test_character_chat_transport.py`、前端store/SSE测试与角色独立e2e文件；文件名随实现记录，不能把尚不存在的命令写为通过。涉及UI切片运行一键检查和完整既有Playwright套件，不删除旧覆盖以换通过。

故障矩阵必须包括：pending写失败零模型；模型成功但commit写失败旧历史保留；replace已完成而终态断线仅一次提交；cancel与commit两种顺序；旧attempt结束晚于新attempt；重试token重复；同action不同内容；revision变化；双会话相同角色不串账；源卡删除/更名；再生成失败原回合仍在；undo同步撤消息与账本；未授权来源/可见性拒绝；恶意JSON体积与慢消费者；运行时设置变化不改变在途快照。

补充主审验收：连续两次regenerate再undo，各生成action归档互不覆盖，旧committed不复活；删除后重放creation ID返回410且零资产读取/模型调用，墓碑写失败保留原会话；默认trace/log零私聊原文。

### 真实角色质量与工程测试分开

工程全绿只证明协议和UI。公开发行前，用合成且明确成年、非露骨角色，在同一模型/参数下验证两种表现模式：陌生→熟悉、利益冲突、未公开信息、玩家声称与事实区别、误会纠正、目标连续与玩家行动权。建议6场景×2模式×每场景3轮，共36次角色调用；记录模型/配置/模式、调用数/token、首可见字和总延迟、失败率及人工评价。群聊互作不伪装成首版已验收项。

费用需运行前明确告知并取得所需授权；本设计不访问玩家私人会话或付费API。任何信息泄漏/越权代玩家决定/来源假造样例单独归因修正，不能被“台词更长”或平均文学分抵消。真实服务stream与non_stream至少各一条完整路径；供应商未测则在兼容说明中标未测，不以fake代替支持证明。

## 11. 优先级与真正未决项

- P1当前：R1A→R1B→R2、两种会话表现、可靠私聊状态、流式与非流式显式降级；若出现数据丢失/泄露升级P0。
- P1已完成：F1/U1，证据在`c396700`和22a；不重复实施。
- P2：I1原始字段拆分及开场白精确映射、群聊R3、故事NPC R4、长期记忆/自动总结、局内资产提取。P3：故事内私聊、全员模拟。
- 无需再问玩家的技术选项：上述UUID/单文件/短锁/限额/单次调用/模块划分/默认messenger均按本契约实施，可随证据调整并记录；不能借调整增加费用或扩大来源可见性。
- 真正需要以后确认的产品选择只有发行时点/是否打包发布、真实付费评测预算，以及超出本MVP的新玩法。当前两种表现模式已确认，不再当阻塞；没有要求用户决定JSON解析器或每步API细节。

本轮仅新增/更新设计文档，未执行运行测试、未改版本/代码、未打包或发布。历史F1/U1的412/35/22结果不归于R0。
