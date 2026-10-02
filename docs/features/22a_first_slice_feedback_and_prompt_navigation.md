# 首阶段可实施设计：F1 反馈一致性与 U1 提示词导航

日期：2026-10-01；验收：2026-10-02。设计：Astra；编码与验证：6.1 Sol。状态：F1、U1 已实现并通过工程验收，未提交、未发布。上级需求见[文档22](22_character_mode_and_state_design.md)。角色引擎、流式传输和迁移不在此冻结范围。

## 0. 代码事实与边界

- 基准 `00ee141`，版本 `1.6.0-dev.16`。`FeedbackSettings.vue` 已有预览/复制/ZIP/Issue；复制和 Issue 仅在 preview 为空时刷新，Issue 标题却读取当前表单，会拼出不一致快照。
- `DeveloperSettings.vue` 直接 select/loadPrompts 覆盖 draft；已有任务分组、变量搜索/说明、扩大编辑、恢复默认、只读权限和开发者锁。不能把“增加分类”实现为丢稿切页。
- 首切片不改变后端 API、prompt ID/文本/优先级/变量/覆盖格式/manifest、模型请求数量、故事存档与角色卡；不升级版本，不支付模型测试，不提交/推送/发布。
- 依次实施 F1 → U1；各自独立测试。若实现揭示需改后端协议或身份/流式协议，停止该扩展并回报，不自行借此做角色引擎。

## 1. F1：一次操作、一份快照

最短路径：设置→“反馈与诊断 · 已实装”→填写→复制/导出/打开 Issue→玩家在外部渠道手动发送。设置菜单入口也标记已实装；辅助说明“仅在本机整理，需手动发送给开发者；不会自动提交”。打开 Issue 只是外部预填网页，仍需用户提交，禁止“已送达/已提交”措辞。

### 操作契约

1. 每次生成预览、复制、打开 Issue、导出均在点击瞬间深复制可提交字段（包括 selected_log_ids），生成稳定 fingerprint；title 与 body 必须来自同一份快照。
2. 采用简单保守策略：复制与 Issue 每次调用 preview API，不复用旧预览。busy 同步置位覆盖整个操作（包括剪贴板）；事件函数也检查 busy，不能只靠按钮 disabled。导出始终调用 export API，独立快照，同样不复用预览。
3. 请求期间允许表单编辑，但禁止重复操作。若请求返回时 fingerprint 已不同，旧结果不执行复制/打开/下载、不成为当前预览，提示“内容已修改，请重新生成”；此策略也适用于导出。UI可保留旧预览但必须立即标记已失效并隐藏其可用状态，推荐直接清空。不得把旧快照的成功提示留在新表单上。
4. 请求启动即清除上次 error/message、作废旧 preview。异常时保留表单、不回用任何旧结果；剪贴板错误有明确可见提示，不误报复制成功。 finally 解除 busy。
5. Issue 使用快照 title 和同次结果 markdown；blocked_by_secret_scan 时禁止打开。保留既有脱敏/秘密扫描语义，不把其他动作的权限扩大。未勾选日志始终为空数组，分类切换/失败/重试不得自动勾选。
6. 异步 window.open 可能被浏览器拦截：提供同一安全URL的显式“继续打开预填 Issue”链接（target=_blank、rel=noopener noreferrer）；不要自动发送网络提交。不预开空白窗口，避免失败泄漏无用窗口。表单变化后废弃该URL。
7. ZIP返回后才创建 object URL，下载后释放；过期请求不创建下载。卸载组件后结果不触发剪贴板/窗口/下载（操作世代或 disposed 标记），不把旧设置页动作带到新页。

### 文件边界

- `aliveworld-ui/src/components/settings/FeedbackSettings.vue`：动作协调、失效提示、可见文案。
- `aliveworld-ui/src/components/modals/SettingsModal.vue`：仅反馈入口文案。
- 可新增 `aliveworld-ui/src/utils/feedbackOperation.js`：纯快照/fingerprint或可注入依赖的动作协调，服务于真实组件，不写仅测试复制逻辑。
- 保留 `src/api/feedbackApi.js` 与 `api/v1/feedback_routes.py` / `core/feedback/*` 语义。确需API错误包装时只作现有响应适配，不引入上传服务。

### 必须通过

- 预览 A→修改标题/正文/日志选择 B→复制、Issue 各取得 B，title/body 同源。
- 控制 Promise：请求 A 挂起→编辑 B→完成 A，零剪贴板/窗口/下载，显示重试提示；再发 B成功。导出执行同一测试。
- 旧成功后新请求失败，零旧摘要输出；clipboard 拒绝无假成功；busy重入只有一次请求；离页后迟到结果无副作用。
- blocked_by_secret_scan 不打开 Issue；未知错误不显示秘密/原始异常载荷；无日志选择的请求仍不带日志；沿用脱敏专项回归。
- 浏览器验证可见“已实装/需手动发送”、编辑后新内容与失败提示，拦截 popup/clipboard/download 不向真实GitHub发提交。

## 2. U1：导航分类不改变提示词执行

默认“游戏”，顶部四个按钮/标签页“游戏｜角色｜工坊｜通用”。筛选的是现有切片列表；仍按 task 分组，原始API顺序不变，无副本注册。分类帮助用户找切片，不是启用/禁用开关。

冻结的纯前端映射（按 task，不按 title）：

| task | 分类 |
| --- | --- |
| `story.*`、`world.capture`、`undercurrent` | 游戏 |
| `character`、`character.*` | 角色（当前无切片） |
| `workshop`、`workshop.*` | 工坊 |
| 其他所有 task（包括未来未知任务） | 通用 |

现有16项全部必须可达（实际数量由注册表测试断言而非硬编码UI）。当前角色页显示“角色提示词尚未接入，暂无可管理切片”，不创建假编辑器；通用无项也显示清楚空态。`undercurrent.core` 属游戏，`workshop.runtime` 仍“尚未迁移/只读”。未来跨模式切片必须补显式映射元数据设计；本切片不假设某个引擎层切片天然适用所有模式，也不添加角色运行提示词。

### 草稿、选择和并发

1. 仅保留一份编辑草稿；dirty=`draft !== selected.active`。切换切片、分类、主动锁定前若dirty，明确确认“放弃未保存修改？”；取消则所有选择/分类/draft不变，确认才丢弃。分类即使仍含当前项也不应丢稿：若当前项仍可见，仅换分类即可；确实离开选中项才需确认。
2. 切换分类选第一个可见项；空分类清空 selectedId/draft，显示空态。点击已选项是无操作，不能重置草稿。允许增加切片名称/ID/task本地搜索；若增加，搜索仅过滤列表，不丢当前编辑（可显示“当前编辑不在筛选结果中”），不引入搜索即自动选中。
3. save 捕获 originId 与 draft，busy期间禁用切片/分类/锁定/恢复、编辑输入/变量插入，避免保存返回重置新编辑；函数同样防重入。保存失败保留原稿；成功后只更新原项基线/覆盖版本，再将该稿标记clean。不使用无条件 loadPrompts 重置所有状态。
4. restore 必须一次确认同时说明将丢弃未保存内容并恢复官方基线，失败保留稿；busy策略同save。只读切片在JS函数与UI双重禁止编辑、保存和变量插入。
5. refreshDiagnostics 只更新覆盖/诊断，不改selectedId/draft。loadPrompts首次或解锁时初始化；后续刷新不能默默覆盖dirty草稿。若所选项消失，先保留草稿并报“切片已不可用”，禁用保存，用户明确放弃才换项。
6. 主动lock dirty时确认，失败不清草稿/假称锁定；成功清掉内存中的切片、草稿、变量详情、提示与诊断。认证失效时禁止保存，保留当前组件内草稿供用户复制，不写localStorage或磁盘；重新解锁/刷新结果也不能静默抹掉它。页面关闭/重载 dirty 使用 beforeunload 原生提示；设置模态框关闭、设置分类跳走导致组件卸载需通过父级可取消的离开guard（而非 onBeforeUnmount 中确认，后者无法可靠阻止卸载）。不新增跨重启草稿仓储。
7. 保留变量过滤/搜索、扩大编辑、恢复默认、readonly契约与现有开发者口令边界。扩大编辑中的输入也遵守busy和dirty，不能成为旁路。

### 文件边界

- `DeveloperSettings.vue`：分类UI与编辑生命周期；新增 `src/utils/promptNavigation.js` 负责纯分类/可见列表，必要的草稿控制器单独模块；仅在真实重复时抽公共工具。
- `SettingsModal.vue`：开发者设置离开guard，保持其他设置现有行为。如扩大编辑组件无法禁用busy，仅最小扩展 `ExpandableTextarea.vue` 透传禁用语义，不做通用重构。
- 不改 `core/prompt_studio.py`、运行builder、覆盖文件格式或后端权限；分类是展示派生数据。

### 必须通过

- 单测覆盖当前所有task映射、未知task→通用、空角色页、原顺序、并集完整且单页无重复。分类前后输入切片对象/请求组装fixture不变。
- dirty选择/分类/lock分别测试取消与确认；同项点击不丢稿；保存失败保留、保存等待期无编辑/切换竞态；诊断刷新不重置draft；恢复失败保留；父级设置关闭/切页可取消。
- 浏览器完整走官方切片→编辑→取消离开→保存→分类往返→版本仍正确→恢复；角色空态无编辑器；工坊只读；未迁移标识仍真实；变量说明/扩大编辑仍可用。
- 更新现有 `full-player-loop.spec.js` 定位：先选择游戏分类再点击 `undercurrent.core` 等原切片，不能依赖全部平铺；不删原提示词注入/恢复断言来迁就UI。

## 3. 交付证据与停门

### 2026-10-02 实际验收

- 实现：`feedbackOperation.js`管理快照、失效、busy与卸载；`promptNavigation.js`只派生分类；`promptDraft.js`管理单稿、失败、认证与锁定生命周期。真实组件接线；父级设置关闭/分类跳走使用可取消guard，扩大编辑继承busy/readonly属性。后端API、提示词注册/正文/装配和存储格式未修改。
- `node --test tests/feedbackOperation.test.mjs tests/promptNavigation.test.mjs`：35/35通过。覆盖四种动作过期后实际新快照重试、卸载零副作用、剪贴板失败、秘密扫描、日志opt-in、注册并集/顺序、dirty确认/取消、失败保稿、保存竞态、认证失效/重解锁、诊断刷新、切片消失与锁定清空。
- 后端专项：`.venv/Scripts/python.exe -m unittest tests.test_feedback_diagnostics tests.test_prompt_studio tests.test_story_prompt_builder tests.test_settlement_prompt_sections -q`，34/34通过。一次初始专项命令误写不存在的`test_prompt_variables`模块而失败，已按实际文件名纠正；不是产品回归。
- `tools/run_checks.ps1`：Python412/412、前端可见性检查、Node35/35、生产构建129模块通过；另一次`unittest discover -s tests -q`确认412项通过。
- `npm run test:e2e`：完整Playwright/Edge22/22通过（1.4分钟）。保留原资产提示词注入/启停、重试/撤回等断言；开发者用例新增切片/分类/锁定/父级跳走/关闭取消、同项不丢稿、分类往返覆盖版本、角色空态、工坊只读/未迁移、401只读稿可选择复制与父级确认离开；反馈验证已实装/手动发送、编辑后复制与Issue同源、被拦截窗口fallback及失败不输出旧摘要/原始异常。
- `git diff --check`通过；只有现有LF/CRLF提示。主线程审阅后纳入本地Git提交；无付费模型、真实GitHub反馈提交、版本变更、打包、push或发行。F1/U1停门达成；R0/R1/R2与流式协议仍待Astra详细设计。

新增前端测试可用 `node --test tests/feedbackOperation.test.mjs tests/promptNavigation.test.mjs`（具体新增文件名随实现记录）；先窄测，再 `tools/run_checks.ps1` 和完整 `aliveworld-ui` 的 `npm run test:e2e`。执行 `tests/test_feedback_diagnostics.py`、prompt相关Python回归，证明现有权限/脱敏/装配未变。无需付费模型或真实反馈提交。

实现后在文档22/活动目标/路线图/CHANGELOG/TESTING写真实结果、未过项与文件，不把本文设计验收当运行结果。实施代理不自行提交或发布，由主线程审阅后本地提交。F1/U1达到契约后停止，不自动继续角色身份迁移、对话引擎、外部格式增强或流式传输；这些需各自可执行协议和夹具设计门。
