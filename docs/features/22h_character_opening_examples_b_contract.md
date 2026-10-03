# B：作者开场与原生行为／对话示例工程契约

主任务阅读补记：本文已完整阅读；旧登场情境迁入scenario是显式草稿转换默认，不能自动迁移既有卡或会话。B1先做开场闭环，B2编辑再按其写入/工坊恢复依赖拆分验证，不借此重构全部资产系统。以下最初设计状态是历史，实施状态见补记。

## B1实施补记（2026-10-04）

- 已实现独立opening领域校验、可选创建参数/旧指纹兼容、同ID重试先读快照、两条写路径冻结、详情/摘要及独立author_opening请求数据区。不增加正式回合、消息证据、账本或供应商调用。
- 前端独立开场编辑/显示组件，默认空、主动读取完整v1卡first_message、覆盖确认、大屏编辑；列表标“预设”。创建在store冻结payload与ID，未知响应时只能显式核对/重试原请求，未确认前不开放改稿产生新尝试；确定输入错误后允许修订。
- 创建待确认状态只在本次应用运行的store保存，不把开场草稿写入浏览器长期存储。彻底重载/退出应用后，应先核对会话列表，不宣称跨重启持久请求恢复。本片不提供创建后修改开场、运行开场宏或自动复制旧starting_scene。
- 开场必需预算不裁剪；示例整段省略以安全字段元数据通知当前界面。来源/引用验证不是自然语言蕴含判断，不保证真实模型不误解预设动作，后续人工质量验收仍独立。
- 窄测Python11/11、前端3项新增、生产构建144模块、B1浏览器1/1及宽窄图检查通过。全量与提交证据以TESTING/活动目标最终记录为准。B2仍未实现；版本/旧ZIP/GitHub不变。
- 最终全量Python511/Node79/可见性/144模块构建及完整浏览器33项通过（3.0分钟），B1达到本片工程停止门。下一B2先结构编辑再写入/工坊可靠发布，不把B1来源隔离宣称为完整角色心理或长期记忆。

日期：2026-10-04。后端核查基准：`8e017ec` / `1.6.0-dev.18`；设计完成时主任务报告 A 已提交 `3714a5b`（Python500/Node76/Playwright32，未改后端／版本／包）。本文件只冻结 B 的最小工程方案，不是 B 实现、测试通过、开场产品扩展或发布授权。承接 [22g](22g_character_chat_acceptance_design.md) 与 [22f](22f_character_card_semantics_i1.md)。

## 1. 主线、确认与默认决定

最终目标仍是一对一角色聊天，角色忠于自身设定、知情范围与共同经历。I1 和 dev.18 包已有验收记录；A 已由主任务完成，B 本轮仅设计，不自动启动实现。下一可验证切片是 B1 开场创建／投影／证据测试，再 B2 卡片编辑与工坊。B 达到本契约、无 P0/P1 后回 C 的世界书／偏好设计，再回 M；不自行开启长期压缩。

已确认需求（P1）：创建时可设置 AI 第一段话，默认空，可主动采用卡片 first_message；不回写卡、不影响旧会话；作者可独立编辑“情景→行为／对白”示例，兼容 mes_example；旧 source 与冻结快照保留。作者文本不能证明玩家已行动，不伪造用户回合。

以下是本片可逆默认决定，**不冒充用户逐项确认**：开场创建后不可单独改写／撤回／重生成；示例沿用 v1 单个自由文本字段；原生自由卡启用示例须显式启用独立字段；卡片旧文本编辑不得再静默清除结构；开场常驻后续请求且不可预算裁剪。若用户要“开场也是可改写的历史消息”，必须另过生命周期／派生记忆失效设计门，本片不预建该能力。

本片无阻塞性人类选择：上述默认不替用户填内容，转换须在 UI 显式确认。仍待未来人类决定的是会话开始后改开场／分支、可执行行为脚本、多条结构化示例与长期记忆，均不进入 B。真实模型是否自然模仿示例、是否误认预置动作属于之后的人工质量验收，不能由合成测试宣称解决。

## 2. 有限核查事实与责任边界

- `core/character_profiles.py` 严格校验 v1 五字符串；`dialogue_examples` 已独立投影，first_message 仅详情可见。旧 description/starting_scene 变动会写 role_fields:null，这条 I1 降级路径在 B 必须改为显式操作，不能无声丢示例。
- `models.py` 会话 schema=1、创建 revision=0、turns/ledger/requests 空；`repository.py` 创建幂等／墓碑／原子写，save 与 transaction 各有冻结字段检查，二者均须加入开场。
- 创建 API 的 fingerprint 当前只含创建参数；UI store 每次 create 新建 UUID。B 的开场参数必须进入 fingerprint，未知成功的重试必须复用创建 ID。
- `context.py` 只以真实双方消息构造 history/allowed_messages；`contract.py` 只接受 player_statement/dialogue_event/model_inference 的运行消息证据。B 不放宽此枚举。
- summary 未读水位依赖 latest_ai_message_id/latest_ai_committed_revision，不能借开场填这两个字段。
- `asset_workshop.py` normalize 已保存 role_fields，但 AI_FIELDS 和手动白名单均不允许独立编辑；现有批量操作逐项变动、publish 先检查再替换文件，不等于跨入口 CAS 或多文件事务。需要补齐本片触及的原子性，不能把既有 atomic rename 宣称成防丢更新。

领域纯函数负责开场／角色字段校验及映射；会话 service/repository 负责生命周期；资产写入协调器负责结构权威与冲突；API 只校验映射；store 管请求身份与草稿；专用小组件负责创建开场／结构编辑，CharacterWorkspace 只组合。不引入第二次模型调用或通用资产数据库。

## 3. 开场存储、身份与创建协议

在会话顶层新增可选 `opening`，不放入 turns、requests、ledger，也不把正文藏进 extensions。schema 仍为1，opening 缺失或 null 均表示没有开场。非空对象严格字段如下：

```text
opening = {
  version: 1,
  opening_id: UUID,
  source_type: "author_opening",
  speaker_instance_id: AI参与者UUID,
  content: string,
  created_at: 会话创建时间
}
```

version 必须为整数1；正文最多8000个 Python Unicode 字符，空白文本规范化为无开场；非空文本保留内文，不解析宏／HTML／标签。opening_id 由服务端生成、会话内唯一、与运行消息／动作／回合 ID 不相撞；它不是 message_id，没有 turn_id、committed_revision 或伪 action。仅双方可见，与本会话聊天访问权限一致；没有私有开场或自定义 audience 输入。本地 owner 为会话，删会话时随现有墓碑流程删除，不产生全局资产。

创建 API 增加可选 `opening_text`（字符串；缺失视为空，非字符串拒绝），其他客户端不能提交 opening_id/source_type/speaker。UI “使用角色卡开场”只是将当前选卡安全字段复制至可编辑草稿，最终发送文字；不是服务器稍后重新读取卡片的指令。切换 AI 卡不自动替换已输入文字，提示它仍为当前草稿；按钮覆盖非空稿需确认。按钮只从有效 role_fields.first_message 读取，无结构旧卡不从 source 或 starting_scene 猜测开场，用户可手工填写。

开场和人物／世界快照、fingerprint、revision=0 在一次 repository.create 原子写内提交。创建不调用供应商，turn_count=0、ledger/requests 仍空。fingerprint 用规范化后的 opening_text；缺失／空／纯空白等价。无开场时继续使用原指纹算法，兼容旧创建 ID 的重试；非空时把 opening_text 纳入指纹。同 ID 同内容返回已保存快照和原 opening_id；同 ID 改文案拒绝 IDEMPOTENCY_MISMATCH，即使卡片已改／删也先查已存会话与墓碑。

store 在一次创建尝试中冻结 payload+client_creation_id，按钮忙碌防重复；网络超时／响应丢失保留这对值，显式“核对／重试创建”复用它们。编辑新内容应显式开始新尝试，提示旧请求结果仍须核对，不能静默生成多个会话。保存失败保留草稿、零模型调用、无半个开场；并发创建由既有同 session_id 存储锁裁决，返回胜出者保存的 ID。

## 4. UI、摘要、上下文、证据与预算

最短路径：选择角色→展开“角色开场（可选，默认空）”→手填或点击采用卡片→创建。空则玩家先发言；非空在第一轮之前显示 AI 侧气泡，固定细标“预设开场”，时间为真实 created_at。渲染用独立 opening 行，不制造用户占位气泡；复制纯文本可以，重生成／撤回操作不显示。详情白名单返回 opening，不返回原 source。

列表无正式回合时可用开场生成160字符纯文本 preview，并增加 `last_message_kind: "author_opening"` 供界面标记“预设”；无开场为 null，正式末条为 `"ai_reply"`。last_activity_at 为创建时间或最新正式回合时间。latest_ai_message_id/latest_ai_committed_revision 在仅有开场时仍为 null；未读只由正式回复推进，创建／重载／撤回最后一轮回到开场均不得产生未读。开场不得占正式历史分页、回合容量或最后一轮操作目标。

每次请求把有效开场置于独立 user 数据区 `author_opening`，白名单包含 content、source_type、speaker_instance_id；**不投影 opening_id 到消息证据集合**，不放入 history，不模拟 assistant 历史消息。固定引擎说明：这是作者预设的角色开场／情景语境，不是玩家动作、同意、承诺或双方亲历事实；当前正式玩家消息及正式历史才能提供对应来源。卡 first_message 除显式复制产生的会话 opening 外仍不自动注入；玩家卡 first_message 永不成为 AI 开场。

开场／示例／source 永不加入 allowed_messages/projected_entry_ids。模型直接引用 opening_id、虚构 user ID、author_opening source 的 ledger_ops 一律拒绝。不得创建“开场已接受”账本、关系或默认知识。本轮真实玩家明确确认时，仅以玩家自己的正式文字提供证据；真实 AI 回复重复作者陈述不能自动证明玩家行为。固定规则须禁止这种证据洗白；现有逐字匹配只能校验来源与引用，不是自然语言蕴含判断器，不能声称彻底阻止模型曲解，亦不为此增加审查 LLM。

开场是已展示且冻结的起点，作为本片必需上下文整段计费／预检，不能为塞进模型而静默截断或撤掉。预算仍先权限过滤，再依次删相关世界条目→整参与者 dialogue_examples（固定顺序）→最旧完整回合（至少保留现有最近2轮）→可选账本；必需人设、当前输入和开场超限则 CONTEXT_LIMIT、零供应商请求。无预算限制的创建可成功，首轮若不适配须明确保留草稿并提示；不偷改已创建开场。省略示例的 UI 原因显示“本次上下文预算不足，示例整段未发送”，只含字段名／参与者标识，不泄漏正文或私有记录。

## 5. 撤回、重生成、旧会话与坏数据

send/retry/regenerate/undo 继续只对正式 turns/action 生效。仅有开场时撤回／重生成无合法目标，UI禁用、API拒绝；撤回最后一轮保留原 opening，重生成第一轮仍使用同一开场。停止／失败／重启恢复不改开场；迟到响应遵守既有 request_id+revision+墓碑检查。metadata 禁止改 opening；repository.save 和 transaction 都校验它被冻结。

旧会话缺字段不迁移、不写回、不从卡片或快照补 first_message；冻结标记依旧按22f投影。新版 opening 非法/未知版本时安全只读或 SESSION_CORRUPT，不丢字段后继续写，不自动降级为空。读旧会话前后文件 hash 不变。旧程序不能保证理解 B 开场，回退需备份；本片不以旧版本程序会保留未知 JSON 键为兼容保证。

会话卡片修改、重导入、删除、克隆、工坊发布均不改变既有 opening/profile_snapshot；显示的作者开场和资料中的卡片 first_message 可以不同，分别标“本会话预设开场”与“创建时角色卡开场”，不得覆盖彼此。

## 6. 示例编辑：复用 v1，不隐式升级／降级

`role_fields.dialogue_examples` 继续是最多8000字符的单个自由文本，UI 名“行为与对话示例”。可给占位提示“情景：…\n行为：…\n对白：…”，不持久化新数组、行为键、自动抽取结构或 v2。保留其余四字段和 v1 全部上限／总长；酒馆 mes_example 映射仍为该字段，原文中的 `<START>`／角色标签只是文本。示例为倾向参考，非脚本、非历史、非精神内核。

结构卡用完整五字段编辑（可折叠），description/personality/scenario/dialogue_examples/first_message 分开；不允许一边编辑派生兼容 description 一边编辑结构。只改示例时其他结构逐字不变；同 payload 有 role_fields 与过时旧文本仍以结构为权威，统一派生 compatibility。改名字／标签／头像／is_player 不清结构；空示例仍保留 v1，不自动退回自由文本。

**原生自由卡新增独立示例必须显式创建完整 role_fields。** 提供“启用独立字段与示例”动作，先在本地草稿显示映射预览，取消零写入；保存成功才升级资产。默认映射：description=原 description，scenario=原 starting_scene，personality/dialogue_examples/first_message 为空，再填写示例。原 starting_scene 旧 UI 称“登场情境”，不能无声认作角色台词；迁入 scenario 后兼容 description 包含其全文，兼容 starting_scene 由空 first_message 派生。预览明确说明这项变化，用户可自行把其内容移到 first_message，但不能从 source 自动猜测。旧会话不受影响。原 description 超16000或总长不适配时拒绝升级，留存原资产与草稿，要求作者手动分配／缩减，绝不截断。未启用时原自由文本路径继续一等可用。

B 明确取代22f“旧文本改变自动 role_fields:null”的降级默认：对已有 v1，遗漏 role_fields 却真正改 description/starting_scene 的请求返回可识别 `STRUCTURED_EDIT_REQUIRED`，保原件和草稿；未改变旧文本／仅改标签仍可保存且保留结构。只有用户显式“转为自由文本”才能提交 role_fields:null，先保留兼容合并文本为稿并警告独立示例语义将消失。旧客户端不能无声清除新示例；这是写兼容的有意收紧，不是旧会话迁移。服务端无法证明点击动作，必须以显式 null 和冲突令牌为协议，不能仅靠 UI 文案保护。

原 `_external_import.source` 归档只读：任何这些写入口均保留已有 source，不以更新后的字段反写来源，也不从它复活旧字段。故事继续读取派生兼容字段；B 不新增外部导出格式或重新导入覆盖规则。

## 7. 工坊手动／AI白名单及并发原子性

结构编辑走同一个 `coordinate_character_write` 规则，不另建 UI 私有映射。手动允许完整合法 role_fields 与显式 null；结构工坊的手动表单提交完整结构，不再发送可编辑的旧合并描述。自由卡只有人工启用结构后，AI 才能写独立示例，AI不能隐式升级／降级卡片。

AI 使用按草稿形态生成的白名单：自由卡维持 tags/description/starting_scene；v1 卡为 tags/role_fields（完整合法五字段，必须保留未要求修改的值）。v1 不给旧 description/starting_scene 的写权限，禁止 role_fields:null、改 version、未知键、原source、路径／portrait／name。保留既有“只讨论与提案／允许修改草稿”开关；AI提案不自动发布。提示词展示的白名单、领域验证、手动应用提案及normalize必须一致，不能只在 ASSET_FIELDS 加字段。允许完整对象是最小写协议，不意味着模型获得资产元数据权限；长对象输出被截断则失败保草稿，不额外调用修复模型。

一组 operations 先在 detached candidate 上按顺序全部校验／应用，再一次提交草稿与撤销快照；后一个操作非法不能留下前一个半修改。包含结构的undo必须恢复完整结构、兼容文本和操作记录，恢复到原稿后发布不误降级。草稿保存失败内存也回滚，UI保留用户未提交输入。

正式资产写入统一使用规范化目标绝对路径为锁键，在同一单进程 mutation gate 中读当前资产→比较 expected_revision／源指纹→协调／校验→原子替换。全局 `lobby_routes`、局内 `local_asset_routes` 和 workshop.publish 必须共用该目标锁，不只锁各自路由／workshop_id；禁止持锁等待模型。新结构编辑请求带打开时的目标修订指纹，标签请求也须基于当前目标合并而不是 stale 完整表单覆盖结构。工坊source_revision包含role_fields，两个工坊、手动对工坊、AI结果对新草稿均作过期校验，冲突不自动merge、不自动付费重发。缺令牌的旧请求如改结构或显式降级须拒绝；真正仅元数据的旧请求可以锁内精确patch合并。

原子替换文件不等于原子发布多个文件。最小故障协议：发布前持久化内部发布意图（目标/base revision/规范化目标内容hash），再锁内 CAS 写目标；最后保存 published 状态。若最后一步失败，重载时只在目标仍匹配该发布意图时完成状态收尾，不重写资产；目标不匹配则冲突保留草稿，不能冒称“未发布”并盲目覆盖。意图只在工坊持久化中，不进模型草稿／API正文，不存 source。写目标失败保持旧文件与可恢复草稿；undo/apply与publish受同一工坊操作门控制。实现可用等价的可靠提交回执机制，但必须通过这个故障验收，不能用try/except掩盖双写间隙。边界仍为现有单进程服务，不宣称抵御用户外部编辑器／多进程同时改同一文件。

## 8. 最小验收与停止门

只用隔离夹具和假供应商；不读玩家资料、不调用付费模型。B1、B2各自完成窄测试再合并回归，文档不预填通过数量。

1. 空／缺失／纯空白开场；主动复制与手填；Unicode8000边界；非法型／字段；创建0回合0账本0调用；重复ID同文返回同opening、改文冲突、响应丢失重试不重复创建、墓碑不复活。
2. 开场含“玩家已承诺／拥抱／给出秘密”、伪消息ID／宏：只出现在独立数据区，history和allowed_messages无它；引用开场的三种来源伪造均拒绝。明确测试只能证明输入隔离／确定性校验，不能证明语义蕴含。
3. 详情重载、摘要标记、未读零推进、第一轮撤回／重生成、仅开场操作拒绝、模式切换不改开场、冻结字段在save和transaction两条路径有效、旧文件读取hash不变。
4. 开场计入预算；示例整段裁剪原因可见；必需集合超限零调用；私有账本权限仍先过滤；source、外部system_prompt、脚本／内嵌书不泄漏、不执行。
5. 原生自由卡显式升级、取消、超限拒绝；导入卡只改示例／标签／其他字段／清空示例；保存重载结构不丢、mes_example仍兼容、原source不变、旧会话快照不变；旧文本变更明确失败，显式null才转换。
6. 全局／局内／工坊手动与AI两种形态白名单；非法后项无半草稿、undo恢复、未发布不改源、两个工坊冲突、编辑器对工坊竞态、模型迟到结果不覆盖新稿；原子replace失败与发布状态二次保存失败恢复。
7. 浏览器路径：创建空开场→另建带开场→重载／首轮／撤回；原生启用结构→编辑示例→保存→新建会话请求含示例；导入卡工坊提案／应用／撤销／发布，原source与旧会话不变。宽窄屏示例与开场不溢出，A键盘／流式／双表现／失败草稿回归。

实施完成由主任务更新活动目标、roadmap、分类changelog、TESTING与本文状态；本文设计子任务不改这些正在协作编辑的文件。B本身不授权版本提升、EXE打包、提交、push或发布。完成本门后停止扩展；C/M需要各自契约，不借B引入可执行作者指令、长期摘要或多角色。
