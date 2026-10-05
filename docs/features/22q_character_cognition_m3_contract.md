# M3：局内认知索引与有界来源原文召回

2026-10-05，Astra工程设计，基线`e031366`（M2与M4a已交付）。用户授权先设计、评审后实现最小M3；本文件冻结下述范围，不代表代码完成。只设计，不改根状态、版本、包、远程或玩家数据。22l/22o的身份、输出、来源、回滚与预算边界继续有效；本文件只明确扩大**实际投影的旧正式消息证据集**，不扩大dialogue_event。

## 1. 可交付结果与真实边界

玩家在共同经历中可按“对方明确说过/对话发生的事/角色推测或意图/作者语境”和已有对象身份查看当前有效认知；仍能点开合法来源、标重要/取消自动选取和纠正。旧话题再次出现时，系统除了原来的账本摘要，还可带上少量对应正式原文，让本次模型看见其原始限定语，并形成有来源的修订。

这是**账本结构索引＋沿来源链接召回**，不是语义搜索、心理侧写、全历史全文搜索或详细偏好建模。代码不从自然语言抽取“甜食”“睡前”等语义对象、条件、例外、喜欢/讨厌方向；这些只在原content和消息中保留，不伪装成确定标签。索引对象仅现有about_instance_id；未填写显示“未指定”，不猜指向真实玩家。已有M2 explicit_preference也只表示模型提议分类，不等于程序证明了现实偏好。

当前会话/角色实例独占，不跨同卡会话共享；C2仍只读、不回写全局偏好。无额外LLM调用、向量/embedding服务、后台摘要或离线任务。原文与ledger仍是权威，派生索引可随时重建；不新增第二份事实文本。

最小片含可见索引和来源召回报告，不能只完成后端。容量仍active128/ledger2048/turns512/32MiB，原文召回不解除这些上限。C3结构化OOC、C4气泡与C5主动联系不进入本片。

## 2. 纯索引与合法修订链

新增独立领域模块（例如cognition.py），从当前已验证会话构建请求内索引，不持久化、不写扩展、不修改原entry。最多检查2048条ledger、512个正式回合/1024条消息，候选最多128个active；这是现有容量内的有界链接核对，不枚举其它session或archived_turn。

内部行只引用已有字段：entry_id、subject_instance_id、about_instance_id（缺失为null）、kind、source.type、source.message_ids、合法root_entry_id、直接supersedes_entry_id、现有memory_annotation.reason（无为null）。展示需要content时从同一权威entry读取，不存索引文本副本；索引不加入虚构的情绪/关系分数或“已确认用户事实”。

有效性至少复用M1 valid_candidates，并核对：active、subject=本AI、AI在audience、created_turn仍正式、每个非author来源message_id当前正式存在、证据引文仍为对应消息逐字子串、消息可见性覆盖entry受众。作者来源可显示为作者语境，但不能参与原文召回或变成玩家陈述。

修订链复用/抽取annotations.chain_root的同subject/kind/about、不扩大visibility、前项superseded、最多2048步与循环检查。建议本次构建一次by_id并记忆化链结果，避免每个候选重建全集。链损坏不猜根、不把旧superseded项恢复成active：该项不进入M3索引/召回，原M1验证/错误路径继续有效；非法存档仍由repository拒绝，不借索引容错允许写入坏数据。

索引只呈现当前active项；root和直接前项ID说明存在修订，不新增历史全文链浏览。合法撤回使原项恢复后，下一次重建自然恢复。过时结论不进入“当前认知”，但正式旧原文仍是“当时说过”，不被改写成当前事实。

## 3. 请求与提示词版本，不改变reply输出

本片不增加reply.v3，不改reply.v1的两键或reply.v2的三键，也不增加ledger kind/source.type。已有parse_result、stream preview、transport对输出版本的严格边界保留。

另定义输入证据契约：`character.context.v1`为既有近期history+ledger；`character.context.m3.v1`为本片，增加recalled_sources。新启动的send/retry/regenerate attempt固定采用m3上下文；已保存旧attempt缺字段解释为context.v1。新attempt保存`context_contract_id`，与reply_contract_id独立；未知类型/值在provider前失败关闭并给`CONTEXT_CONTRACT_UNSUPPORTED`（409、不可自动重试）。retry_input保留原上下文契约便于追溯，显式重试作为新attempt记录当前m3，不改写原attempt。只读旧存档不补字段或迁移。

新m3上下文作用于以后请求，包括仍采用reply.v1的旧会话；不自动启用其M2高光、不升级memory扩展。没有额外收费、跨身份或历史数据写入，无需新增功能许可开关；UI说明“本次可能携带最多4条关联旧原文”。旧attempt/旧context可在兼容测试与恢复核对中按原投影构造，不能让升级后重启默默改变pending含义；沿现有启动中断策略，不自动恢复模型调用。

提示词注册独立m3身份，建议两个任务集合`character.reply.m3.v1`、`character.reply.m3.v2`，各含独立`.core/.contract/.presentation`三片；输出plan.contract_id仍原reply版本，trace/模型路由仍character.reply。复用旧基线常量生成新文本可以，但新slice ID不得继承旧v1/v2本地core覆盖。旧覆盖保留可见、不删除不自动复制；工作台说明旧覆盖未应用到m3，用户可显式复制编辑新core。contract/presentation维持原不可编辑属性。manifest须明确真实新slice及context_contract_id，不把新语义藏在同名旧切片。

新文本必须说明：recalled_sources是过去正式对话，不是本轮新事件；索引/注解重要性不提高可信度；当前纠正须结合适用范围，不把相反句子机械都当当前事实；原文可保留场景/例外但不得猜现实属性；dialogue_event仍只能引用本轮正式user/reply；ledger旧引文本身仍不是额外合法message。输入数据增加context_contract_id作为明确标识；不能从用户正文猜版本。假供应商也按明确契约/投影生成测试结果。

## 4. 原文召回候选、限制和闭包

先按原M1/M2 select_memory确定最多32条账本（intent最多8，手动/自动16等规则不变）。**只沿这些已选有效entry的source.message_ids找正式原文**；最多64个引用，不为没有账本来源的旧消息做搜索。正式消息字典只用于按ID查找，不遍历所有消息正文做全文检索。

仅在当前输入与entry.content词法单位有交集时考虑关联原文；复用M1 NFKC/casefold、英文数字整词/中文双字、查询最多128单位。无交集的手动重要仍按M1常驻优先，但不因此每次携带旧全文。无查询单位则不召回。候选entry顺序沿本次select_memory稳定顺序，不另外调用语义模型或用私有心理评分。

一个候选组对应一个entry所引用的全部1–2条消息，已在初始近期20回合history的部分无需重复携带。其余为待召回消息。只接受本会话正式且AI可见的完整消息，白名单投影同history必需字段：message_id、turn_id、speaker_instance_id、content、presentation_mode、visibility、created_at。不传附加extensions/attempt/私有元数据。source为author、空引用、缺失消息、取消/失败/archived消息一律不形成候选。

冻结上限：总计最多**4条不同完整消息、4000个Unicode字符content合计**（与既有text长度口径一致，另受总token预算）；单条超过4000直接不选，不截头尾、不只取匹配句。按候选entry顺序尝试组，已选message_id去重，计算新增消息数量/字符，整组可容纳才加入；不合则跳过本组，继续尝试后面的更小组。记录每组的支持entry与引用闭包，不把同一消息当多份证据。

不同entry共享来源可复用同一消息，但不能因它被私有entry关联就公开私有entry存在。消息本来公开不代表其私有意义可公开；报告按公开支持entry过滤，而不是仅看消息audience。

闭包定义：一个原文组可留在最终recalled_sources，仅当至少一个支持entry仍在最终ledger、其全部来源引用都位于最终history或最终recalled_sources、且完整组消息仍满足权限/正式性。被裁剪的parent不能留下“孤儿原文”。本片不要求每个ledger项的旧引文都出现在allowed_messages：没有召回的旧ledger仍可作为既有记忆，但不能据其引文制造新证据。

初始history中的消息以后被预算裁掉，不会因此动态补进recall；保持候选单调减少，避免裁剪—重选循环。若这使某组引用不完整，移除该组；共有消息只有仍被其它完整有效组支持才保留。重复计算至稳定（最多原候选组数次），不从已跳过候选补位。输出recalled_sources按首次选入顺序，稳定去重。

## 5. 预算裁剪与最终证据

输入数据在m3模式下总是含`recalled_sources`数组（可空）；不发送第二份全量cognition_index，ledger原字段已足够表达认知身份，派生索引服务本地取材/UI。context.v1保持旧输入字段/证据集合，不暗中加recall。

总预算仍使用实际提示词、完整history/ledger/recalled_sources统一计算。裁剪顺序冻结：可选C2偏好→世界普通条目→对白示例→低优先原文组（反向候选顺序，组级剔除并重新去重）→近期完整回合直到至少2轮→低优先ledger整条。每次变化都重新闭包，原文不因后来释放空间而回填。必要人物/系统规则不裁，全部可裁内容移除仍超限则CONTEXT_LIMIT且零provider调用。

这样原文只作为额外证据增强，不能为保4条旧原文先挤掉近期对话或手动重要账本。一个组被裁但其消息仍由另一个组支持时，直到最后一个支持被移除才真正减少载荷；测试须覆盖共享源，不能用组数量假装实际token减少。

只有最终预算通过后才构造`allowed_messages = dedup(final_history + final_recalled_sources)`，由同一个冻结request传给plan_turn；projected_entry_ids也只取最终ledger。不得使用初选消息、UI来源查看缓存、原始全档或budget前的集合。report、实际输入、allowed_messages必须同一次最终投影一致。source允许的是正式消息原文，不是索引字段或界面标签。

player_statement仍只能引用玩家消息，model_inference只能支持belief/intent/relationship，experience/dialogue_event仍仅本轮user/reply。引用被裁旧源、非投影旧message_id、伪引文或跨会话来源整轮CONTRACT_INVALID，不能删坏op后保存正文。supersede目标仍必须在最终ledger且同kind/about/subject和不扩大visibility；召回一条旧消息不授予任意旧entry修订权。

提交时依已有base_revision/attempt权威门；在regenerate副本先撤旧回合，再构造/核验正式消息映射。冻结allowed_messages须能逐一核对到该候选的当前正式来源（ID、speaker、content、visibility一致），不信任客户端传入任意消息数组。用户API不接受自定义allowed_message_ids/recalled_sources。

## 6. UI/API与安全报告冻结

最短入口：共同经历内新增折叠“本局认知索引”，无需另开页面。默认全部当前公开项；可按来源类型和对象（当前用户/当前AI/未指定）筛选，并展示现有kind及M2原因标签。对象是局内参与者，不写“真实用户画像”；关系/信念明确为角色理解。每项使用原记忆content和已有来源查看/纠正入口，不新增无来源直改/确认事实按钮。

新增只读`GET /api/v1/character-sessions/{sid}/memory/cognition`，不接收query/body/任意entry过滤参数，返回全部最多128个**公开有效**索引行，由前端本地筛选。严格响应：

```json
{
  "version": 1,
  "session_id": "UUID",
  "revision": 0,
  "entries": [{
    "entry_id": "UUID",
    "about_instance_id": null,
    "kind": "knowledge",
    "basis": "player_statement",
    "root_entry_id": "UUID",
    "supersedes_entry_id": null,
    "annotation_reason": null
  }]
}
```

basis仅author/player_statement/dialogue_event/model_inference；kind沿既有五类；annotation_reason仅M2枚举或null。无content/source全文、私有数量、漏掉条数、词法得分。entry_id必须存在于同revision的公开ledger；前端若revision不一致重新取session/索引，不用旧row指向已撤回文本。API读取不修改文件，未知版本沿既有拒绝语义；有合法公共后继的root/前项按链可公开，不返回私有后继。只在展开、session切换或正式修订后按需刷新，不后台轮询。

本次取材说明新增可选`source_recall_report`，沿accepted和最终生成响应传递，严格为`{version:1, entries:[{entry_id,state}]}`。只包含有旧原文候选的公开支持entry，每ID一次，最多32项；state仅`sent`（完整组最终有原文实际投影）、`budget`（初选通过4/4000后因预算或最终闭包失效）、`limit`（完整组超4/4000，未初选）。与初始history完全重合的组不报告为旧原文召回；私有支持不产生公开行。对共享源，public组只有本身完整闭包成立才报sent，不以其他private组送入某一条就宣称其完整。

报告不返回message_id、引用正文、来源数量、内部全部候选数或私有entry。UI用原公开entry简述，链接既有合法sourceLoader查看当前来源；注明“已送入请求不等于模型一定采用”。消息窗口变化导致原文只在近期history时，不误报召回失败。无报告/重载显示“尚无本次原文取材信息”，不从当前索引伪造上次成功。

报告生命周期同现有memory_context_report：请求内冻结，store按session/request身份处理；切换、撤回、删除、新请求清理过时报告，迟到SSE/HTTP不得污染另一个会话。必要安全规则不依赖该报告。

## 7. 持久化、撤回与失败

索引和recall计划只在请求冻结job/内存保存，不保存原文副本、语义标签或第二份账本。持久变化仅新attempt/retry_input的context_contract_id；不修改memory v2、不添加全局索引或m3 session开关。正式op若成功使用旧源，按既有ledger.source保存1–2条message_id及短引文，仍受原限额和inverse。

撤回/重生成先从正式turns排除旧分支；派生索引、候选、允许消息均重建，archived原文不能重新引入。失败/取消不新增账本，存盘失败保持原子事务与现有blocked恢复，不恢复旧候选继续调用。上下文契约未知或来源不闭合须调用前错误；模型输出非法引用则可能已经消耗本次调用，但不自动收费重试。

关闭会话、删除、切换权限不复制索引到其它session；诊断默认不导出原文/完整上下文。新场外控制尚未实现，本片既不把普通括号猜成OOC，也不承诺已隔离未来OOC字段；C3引入后须明确源类型再接入本索引。

## 8. 验收矩阵与停止门

用隔离合成数据、假供应商验证：

1. 中英文旧话题在20轮之外，来源有更完整限定语：本次ledger命中、最多4整消息/4000字符实际送入，旧玩家陈述可形成合法knowledge/supersede；旧源不能形成dialogue_event。不把token命中叫语义理解。
2. 没有账本链接的旧消息不检索；零关键词不召回；作者开场/示例/world/C2/失败preview/archived/其它session/私有意义不进入公开索引报告。正文中的指令仍是数据。
3. 恰好4/4000、超过一字符、单条8000、两源组、共享源、重复ID、初始history重合、最后budget闭包失效、中文字符与UTF-8 token预算差异；不截消息、不回填、不重复证据。
4. 最终裁剪后actual input/history/recall/allowed_messages/projected_entry_ids/report闭包完全一致；超预算零调用，裁掉旧源后的引用整轮拒绝；模型不得用召回源supersede未投影目标。
5. 明确声明/推测/作者语境按现有source显示，不推断喜欢/讨厌方向、例外或现实身份；合法supersede仅当前项，撤回恢复，非法循环/换about/越权链失败关闭。私有项不露ID/文本/数量/缺失计数。
6. send/retry/regenerate各自冻结context与reply版本；旧无context字段按legacy、未知context调用前拒绝；reply.v1/v2严格解析与流式保持原协议；旧prompt覆盖不注入新m3，manifest可定位新基线；读旧会话hash/mtime不变。
7. 正式提交、撤回、重生成成功/失败、取消、CAS/busy、保存故障、启动恢复、丢响应不借旧来源；当前版本取消/重试仍只有每次显式生成的一次provider调用。
8. UI展开索引→来源/对象筛选→查看原文→发旧话题→看实际召回说明→纠正草稿保留已有输入→合法修订→撤回；宽窄、键盘、流式/非流式、迟到响应/切会话/重载空报告回归。

建议依次M3a纯索引/召回/闭包与context版本、M3bservice/API/提示词兼容、M3c前端最短闭环与完整回归；完成a不能称M3交付。独立领域模块拥有派生政策，context拼装，contract核验，service事务，API/store/UI分层；不把词法/链/预算规则塞入大组件或路由。

窄测后跑Python/Node/可见性/build/完整Edge，主代理更新活动目标、路线、CHANGELOG、TESTING并记录实际证据。自然语言质量仍需真实模型人工验收，本片不授权付费实测。满足上述有界来源闭环且无P0/P1后停止，不顺手开发语义偏好抽取、容量迁移或C3/C4/C5。

## 9. 产品选择状态

此最小片无需新增实质性用户选择：只改善已授权的当前会话记忆可见性及同次请求的有界来源，不增加调用、不自动全局学习。用户已确认的OOC小框/主动联系当前会话授权仍有效，不重复询问。

若要把自然语言自动结构化为“对象—喜欢/讨厌—情境—例外”并可手工编辑/确认，或跨会话真实用户档案、语义检索服务、自动历史扫描、额外模型提取，应另立产品/工程门。不能把本片完成称为这类详细认知已交付。

## 10. 2026-10-06实现与完成审计

M3a/b/c源码完成；主代理对照目标与本合同审计，完整证据在TESTING。Python606、Node109、158模块构建、最终完整Edge38（5.3分钟）与宽窄视觉通过；未增加付费调用、容量、语义抽取、版本、包或远程状态。

| 必须兑现的要求 | 当前权威实现与验收 |
| --- | --- |
| 局内索引、权限、修订来源，非真实用户画像 | cognition.py复用当前正式账本/引文/受众与有界chain_root；只读cognition API仅公开七字段，hash/mtime、非法链/坏数据/隐私专项及UI来源/对象筛选验证 |
| 整组有界召回且不截句/扫描无链接历史 | recall.py只沿选中词法相关账本，4不同整消息/4000 Unicode字符；两源/共享源/超长/作者/近期重合/无链接/零查询/首次顺序专项 |
| 最终预算与允许证据闭包 | context.py按合同组级裁剪，单调无回填；实际JSON与final allowed IDs一致，contract.py再核对正式ID/speaker/content/受众，旧dialogue_event与任意目标/伪造源拒绝；超限零调用 |
| 请求冻结与旧协议兼容 | context_contract.py、models/service/repository/transport与独立M3提示词；send/retry/regenerate/旧pending中断/未知409零调用/旧覆盖隔离/严格reply.v1-v2专项和全量回归 |
| 撤回、取消、失败与并发隔离 | 正式原文映射重建与既有原子提交/inverse；旧源修订→undo、cancel零调用、保存故障无新账本，已有busy/CAS/再生成/异步store与Edge交叉会话回归 |
| 玩家可操作且报告不泄漏 | 独立解码器、折叠索引/原文报告、现有来源/纠正入口；同revision迟到/删除/修订核对/草稿保留、SSE与非流式/重载空报告Node；最终Edge实际超过20轮关联原文+来源链接+修订撤回/宽窄截图 |
| 可维护交付与停止门 | 领域模块/API/client/store/components分层；ACTIVE、MASTER、路线、决策、分类CHANGELOG与TESTING同步、本地Git；C3/C4/C5合同尚未冻结，停在此门 |

真实模型是否正确理解限定语、作者来源或角色心理不由上述工程验收证明，仍需后续人工体验。本轮既无逐题材提示词堆砌，也不将“词法相关”冒称语义理解。既有主bundle约537.38KB警告为P2，未隐藏。
