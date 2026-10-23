# AliveWorld 测试流程

## dev.31实际包与发布（2026-10-23）

- 构建/标签9afccc0ac5b7004a55f809da23857149f9d59a50；build/dev31-package.txt确认主EXE、更新助手、结构/隐私/覆盖保留检查通过。
- ZIP 38,484,594字节，SHA256 `bdccde3df365a74bee9d60aa5414fc7fcb25fc3a94bf1670b9f326df50ec5896`；校验文件107字节，自身摘要 `d62c39f211827149e634f330d224e93f07afbe007a62dc4b5cb9b1e637f7c023`。GitHub API确认非草稿预发布、两附件uploaded且digest均匹配，标签指向构建提交。

## dev.31通知设置（2026-10-23）

- build/worldbook49-python.txt：982 Python全量通过（56.895秒）；build/worldbook49-frontend.txt：155前端通过。
- dev.31生产构建通过。Edge通知与既有历史审阅2项通过（29.3秒），包含实际UI保存、详细默认无正文、明确授权摘录、撤销立即清除、静默仍捕获、重开不补旧通知、刷新载入后设置保留。截图build/worldbook49-notices.png已查看。
- 验收定位并修复本局自动保存复制Vue代理报错；后续测试失败分别为假模型重复同一条目被正确去重、测试使用不存在的“进入”按钮，已改唯一新修订及实际save-load入口。
- 不新增模型调用，测试使用真HTTP/假模型；不代表真实模型质量或纯净Windows实测。实际包和远端附件在完成后补证据。

## dev.30实际包与发布（2026-10-23）

- 构建/标签5f529ea1e57d3379d3e8d9f7ce57ea80ab91e9be；build/dev30-package.txt确认主EXE、更新助手与便携包结构/隐私/覆盖更新保留检查通过。
- ZIP 38,485,213字节，SHA256 `a623f9d60dd8425d34387adf5ca9d83ad9ad559f934b44fea6e0dcc7c8bbdb45`；校验文件107字节，自身摘要 `940d6e9f0f0a28dbe96b64299b7bd83a30d47b457cf551cc0761763f7fe021b2`。GitHub API确认非草稿预发布、两附件uploaded、digest均匹配、标签精确指向构建提交。
- 最终dev.30产物的批量流程再次通过（9.4秒），已查看dev.30截图；源码、分类发布说明与证据同步。

## dev.30冲突批量审阅（2026-10-23）

- build/worldbook48-python.txt：981项Python全量通过（76.168秒）。

- 世界书85专项通过：批量决定、旧单条兼容、重复/缺失ID、请求形状、过期与忙碌、保存失败不部分应用，原书文件不变。
- build/worldbook48-frontend.txt：153项前端通过；npm生产构建通过（既有包体提示仍在）。
- Edge两项通过（15.6秒）：原单条冲突/恢复/撤回流程与新增三书多冲突流程；覆盖选中部分、全部待审、恢复、原书不变且只有一次正文结算模型请求。build/worldbook48-batch.png已查看。
- 不代表真实模型冲突判断质量，也不代表纯净Windows或玩家机器更新实测。实际打包/Release证据在完成后补入。

## dev.29实际包与发布（2026-10-23）

- 构建/标签df6082b004c47a2b0ff0b594d850c6d3e8c35b16，build/dev29-package.txt确认主EXE、更新助手及便携包结构/隐私/覆盖更新保留检查通过。
- ZIP 38,482,778字节，SHA256 `60b54a5d00f015de1b9dcf9bbce4776abcb2763ab626fba75b0ea89527f09e7a`；校验文件107字节，自身摘要 `e89fef66116119b5ca3eebc37a830480316f9ab077b88e1ad05e378943676426`。GitHub API确认非草稿预发布、两附件uploaded、digest匹配、标签精确指向构建提交。
- 最终dev.29前端产物的修订记录Edge流程再次通过（12.6秒），截图显示dev.29且已查看。源码与发布说明同步推送。

## dev.29世界书修订记录（2026-10-23）

- build/worldbook47-python.txt：977项Python全量通过（59.837秒）；最终build/worldbook47-focused.txt：82项世界书专项通过，含同名书精确文件审阅。
- build/worldbook47-frontend.txt：151项通过。浏览器3项通过（27.3秒）：worldbook-activity、worldbook-revisions、worldbook-routing，含真HTTP假模型、首次静默/聚合提示、默认不传正文、详情、原书批量审阅、撤回失效、一捕获调用。
- build/worldbook47-history.png已检查。新增面板默认折叠，展开后有界滚动，详情显式开启。失败定位：首次测试搜索提示符错误，随后真实自动书显示名/文件名不一致的审阅失败已修复。
- 不代表真实模型语义质量、纯净Windows或玩家旧EXE自动更新实测。

## dev.28实际包与发布（2026-10-23）

- 构建/标签e438a10571416203a3014bc67baf2df31fa1d25b，build/dev28-package.txt确认EXE、更新助手及结构/隐私/覆盖更新保留检查通过。
- ZIP 38,475,925字节，SHA256 `5ba92f0ca352e05f8e666edcf6c4fcc7b2c4235e16364e1156e4c6e1958e4b4f`；sha256文件107字节，其自身摘要 `fba6012726849b296927471659bed3d2d02cddec5156cf95f6c64423a446e6f8`。GitHub API确认两附件uploaded、digest一致、标签精确指向构建提交、非草稿预发布。

## dev.28归属验收（2026-10-23）

- `build/worldbook46-python.txt`：971项通过，83.284秒；随后增加关闭自动书测试，最终世界书专项76项通过。
- `build/worldbook46-frontend.txt`：149项通过。
- Edge分别通过worldbook-routing（最终13.4秒，含主题编辑保存）、worldbook-revisions和worldbook-collaboration三个不同用例。真HTTP假模型验证一次捕获请求分入三书，撤回投影全部清除；截图worldbook46-topic/routing已查看。
- 初次主题编辑验收的定位器误把textarea当容器，修正测试定位后通过，不是界面故障。未使用真实付费模型，不声称完成分类语义质量验收。

## dev.27实际包与发布（2026-10-23）

- 构建与标签提交7d3ab5c8b4d6f9bebfb4020944413f3d1c787a92；build/dev27-package.txt确认主EXE、更新助手、便携包结构/隐私排除/覆盖更新保留UserData检查通过。
- ZIP 38,469,055字节，SHA256 d577b8d255034f595c978dd1e62780f947f46046b95aa55bfdfe043705748a2f。GitHub API确认非草稿预发布，ZIP与sha256两个附件uploaded，远端digest分别与本地一致，标签精确指向构建提交。
- 发布正文包含本版分类概要，源码分支已推送。未接触用户游玩区、未宣称纯净Windows测试或真实付费模型语义质量验证。

## 45 多世界书验收（2026-10-22）

- 963项全量Python通过（96.152秒，build/worldbook45-python.txt）；领域、API、存档事务、同ID跨书、来源变动、内容编辑、恢复去重、旧档无主书均有专项。
- 149项前端单元通过，生产构建通过（保留既有分包体积提醒）。4项Edge通过（18.2秒，build/worldbook45-e2e.txt）：3项故事开局回归＋1项多世界书真实HTTP/UI流程。首轮测试因按钮无障碍名称缺少分隔而未找到，补明确aria-label后通过。
- build/worldbook45-collaboration.png已查看：主书按钮、折叠设置/双方依据和恢复入口在右侧世界书本局面板，角落消息不展示隐藏条目内容。使用隔离合成资产，不使用玩家数据或真实付费模型。
- 最后补验下一回合实际请求不含被停用条目，并回归捕获修订和停止流程；实际打包/发布另记证据。

最终补验：3项Edge全部通过（22.2秒，build/worldbook45-e2e-final.txt），涵盖下一真实结算请求过滤、两次撤回来源失效、既有捕获新增/更新/废止/批量审阅、停止改发。回归暴露Windows列表读取句柄与后台原子替换冲突（WinError 5），已用现有世界书锁保护短读取，并在解析前关闭句柄；67项世界书专项随后通过。该修复基于实际失败，不新增模型重试或通用防御框架。

## dev.26实际包与发布（2026-10-21）

- 构建提交7207b1b89fe61bf023517672e95f6f4323cc80c9。build/dev26-package.txt：主EXE与更新助手构建成功；便携包结构、隐私排除及覆盖UserData保留验证通过。
- ZIP 38,454,101字节；SHA256 10b727e819b7f028fe8c7a536812279322966d68fc89c6b2c86537d4a195d5c4。GitHub API确认非草稿预发布，两附件uploaded，远端digest相同，标签精确指向构建提交。
- Release正文来自本版本分类更新概要。未操作游玩区数据；不宣称本次在纯净Windows或玩家旧EXE实际自动更新测试过。

## 44角色长聊交付验收（2026-10-21）

- 952 Python全量通过（71.766秒，build/character44-python.txt）；随后补足最近10组保留用例，22项定向通过（build/character44-focused-final.txt）。149前端单元通过（build/character44-frontend.txt），生产构建179模块通过，仍有既存分包体积提示。
- 10项既有多气泡/主动联系Edge通过。新增真实HTTP长聊闭环独立最终通过（48.9秒，build/character44-longchat-final.txt）：开启费用确认、22组聊天低频整理、来源查看、整理结束后真实后续请求携带摘要、关闭后GET不新增模型调用。合跑最初因测试在异步摘要完成前检查下一请求而失败，补充完成后真实发送，未伪造模型记录。
- build/character44-long-chat.png已查看，入口位于右侧资料的记忆分类。默认关闭、失败停自动整理、关闭取消迟到结果、来源改写失效、原文不变及摘要不扩展证据集合由专项覆盖。
- 使用隔离合成会话与假模型，无玩家私聊上传、真实模型语义质量或纯净Windows声明。打包及远端附件证据另行补记。

## dev.25实际发布（2026-10-21）

- 构建提交24cc0b84ed2eab23a6c89d22e2778e8d1c162bca，主EXE/更新助手与ZIP成功，内置便携包结构/隐私/覆盖保留UserData验证通过，日志build/dev25-package.txt。
- ZIP 38,438,047字节，SHA256 5b9dfbc482b7a8a27345bc743f2e67ca8e3359ce8ccd2f2333a8e4c064e0776c。GitHub非草稿预发布，ZIP与校验附件均uploaded；API digest与本地Get-FileHash一致，标签指向构建提交。
- 发布正文已包含分类更新概要及质量边界。没有在用户游玩目录上执行更新，也没有宣称纯净Windows实测。

## 42最终代码验收（2026-10-21）

- 943 Python、149前端通过；构建178模块通过。修改后前端再次全测149项通过（build/character42-frontend-final.txt）。
- 27项相关Edge分组验收通过：旧格式17项与主动联系3项；新格式7项最终43.0秒（build/character42-groups-final.txt），旧键位专项12.0秒（build/character42-keys-final.txt）。不是声明整个仓库所有浏览器用例通过。
- 首轮新格式失败因未重建dist仍使用旧队列判断；重新构建后真实失败点击重试只增加一次模型请求。旧键位断言还检查已移走的placeholder提示，改为检查真实页脚提示与实际按键发送，未改生产键位行为。
- 截图发现首条气泡菜单向上被聊天滚动区裁切，改为视口范围内定位；重新验收右键、长按、菜单边界和草稿保留，查看character42-failure-menu.png、character42-details-wide.png/narrow.png。
- 单句假模型通过真实HTTP仅生成一条气泡，实际请求包含表达指导；指导覆盖/缓存片身份测试通过。不宣称真实模型文学质量或真实Windows纯净机验收。

## 42角色体验验收进行中（2026-10-21）

- 全量943 Python通过（56.069秒，build/character42-python.txt）；149前端通过（build/character42-frontend.txt），生产构建178模块通过。
- 浏览器首轮发现失败输入也在queued_count内，导致气泡重试入口被隐藏；前端投影及控制器改为遵循服务器retryable。新增待回应失败输入下的重试测试。修改后必须重新构建前端再跑浏览器，不能把旧dist测试作为当前源码结论。
- 旧会话浏览器测试已按四分类更新导航，兼容轮次数据不改。最终浏览器结果及包验收尚待补齐。

## dev.24实际发布（2026-10-21）

- 构建提交e665a0f，真实主程序和更新助手、便携包验证完成（build/dev24-package.txt）。ZIP为38,435,347字节。
- GitHub预发布非草稿，ZIP/校验文件均uploaded；远端digest与本地fb2ea0484a7d3e5b7ffa6d3d8656c4e28508a6ed1c80d66a4358de428ef143a2一致。

## 43发布准备验收（2026-10-20）

- 全量942 Python通过（71.947秒，build/story43-final-python.txt），146前端通过（625.778ms，build/story43-final-frontend.txt）；前端176模块构建通过，既有chunk大小警告。
- 4项Edge覆盖空/手写开场、创建前卡片选择、作者包默认设置和开场、切换来源保留草稿、重名不覆盖、停止/修改重发；最后底部按钮固定后再次复核。
- 后端故障注入证明存盘失败不注册会话且删除本次新目录，旁边旧目录内容保持；缺失资产不建目录，局内角色is_player修改不影响源文件。
- 世界包测试初次使用错误的experience_preset层级被现有验证拒绝，按实际defaults结构修正夹具，未改变生产校验。
- 未升版、未重打EXE、未推送；本次达到“可打包发布”，不等于已完成新包验收或线上发布。

## 43-A故事开局（2026-10-20）

- 939 Python通过，62.570秒，build/story43a-python.txt；14专项覆盖空历史首轮/回滚、手写开场重载、旧description兼容及自动世界书。
- 前端构建175模块通过，既有chunk体积警告。Edge新建/停止两项通过（10.3秒）；查看build/story-start-dialog.png，900×700暗色窗口及操作可见。
- 首次专项断言误将未来/裁定等技术消息也计为用户/AI消息，改为明确检查两种角色；撤回用现有rollback入口。浏览器首次合跑第二项等待不存在的新手弹窗，改为显式关闭新手引导的测试前置后通过。
- 没有付费模型质量测试，没有重新打包。B资产选择未实施。

## dev.23发布门完成（2026-10-20）

- 最终935 Python（72.044秒）、146前端通过；最后六项Edge全部通过（25.6秒），含慢速建立新草稿时输入保留、两次发布、历史开关、重载及停止。
- 最终构建日志build/dev23-package-final.txt，包结构/隐私/覆盖保留UserData检查通过。ZIP 38,434,222字节，SHA256 45be7954e1c331366a3c82b6197173be3406cb53b199cc290e10c9b59e54e7e5。
- GitHub预发布v1.6.0-dev.23非草稿，ZIP和校验附件均uploaded，远端digest一致，标签指向构建提交529f0b4cfe8d2d733ba1820e8c4122dec5425102。
- 未宣称真实供应商的语义质量、纯净Windows启动或用户游玩目录的一键更新已实测。

## 41-B连续创作验收（2026-10-20）

- 收口发现发布状态先返回、资产刷新尚未完成时“继续编辑”可被点击但无效；按钮现在与busy状态一致禁用，避免静默忽略点击。最后变更后重新构建并复核五类工坊与停止流程。
- 最终Python全量935通过（72.044秒，build/dev23-python-final.txt）；六项Edge合跑通过（26.8秒）。追加慢速开启草稿测试发现加载期间聊天区闪空，保留旧检查点展示并保护加载期间新输入后专项复核。
- Python全量933通过（75.478秒，build/dev23-python.txt）；之后新增偏好HTTP显式授权及同名不同路径隔离测试，workshop_context五项通过。前端146通过（build/dev23-frontend.txt）。
- 首轮6项浏览器5通过，最后重载的新手弹窗延迟出现遮挡点击；测试改为等待真实按钮后，世界书跨两次发布/关闭历史/重载场景通过（10.8秒）。不是放宽功能断言。
- 假模型扫描真实请求中的旧讨论标记，确认跨发布携带与关闭后排除；五类Agent原文取材不增加模型调用，长历史预算限制不修改原文。
- 不把程序取材正确等同真实模型能理解全部历史，完整语义召回及文学质量未验收。

## 41-A 工坊阅读验收（2026-10-20）

- 前端生产构建通过；Edge五类工坊审阅、重载、发布测试5通过（22.0秒）。
- 新增专注阅读宽高增加、输入保留、Esc退出、尾部操作位置检查；900×700窗口输入/退出可见且无页面横向溢出。
- 已查看build/workshop-focus-desktop.png及workshop-focus-narrow.png。无后端/提示词变更，不额外重复全量Python或调用真实付费模型。

## dev.22远端发布核对（2026-10-20）

- GitHub Release非草稿、预发布，标签v1.6.0-dev.22指向4255d4d0c12e898f28de17705100533e311a2b94。
- ZIP 38,426,953字节和SHA256文件均为uploaded；GitHub返回ZIP digest与本地abb1d4c4dbbe77f959f23cfb2c8f06b69dfa4bec370286c847ea33cb9b667d93一致。发布正文包含分类更新概要。
- 发布仅复用已验收包，本轮无功能改动；未宣称从旧游玩目录完成真实自动更新测试。Git直连失败后使用Windows现有127.0.0.1:7897代理的单次命令成功，不修改全局Git配置。

## dev.22本地交付门（2026-10-19）

- 8项Edge统一重跑全部通过，57.9秒（character-groups、provider-retry、story-stop、workshop-stop）；旧格式character-mode停止/修改重发专项通过，17.7秒。旧专项补独立角色卡fixture，不再依赖其他用例先执行。
- model_connections＋generation_control 17通过，0.420秒，含新增重试参数范围与请求状态隔离；前述928全量和146前端通过证据仍适用。
- `tools/build_windows_portable.ps1 -SkipDependencyInstall` 成功，重新构建前端、主EXE与更新助手；内置test_windows_portable_package验证版本、结构、隐私及覆盖升级保留UserData通过。日志build/request39-package.txt。
- ZIP：release/AliveWorld-1.6.0-dev.22-windows-x64.zip；SHA256 abb1d4c4dbbe77f959f23cfb2c8f06b69dfa4bec370286c847ea33cb9b667d93。无玩家数据或凭据，旧发布包保留；没有推送/发布远端。未额外宣称纯净Windows真实启动验收。

## 39-B/C集成回归（2026-10-19）

- Python全量：928通过，65.746秒，build/request39-python.txt。首轮发现旧角色取消后任务收尾阻挡新重试，改为按请求观察后完整重跑通过。
- 前端单元：146通过，721ms，build/request39-frontend.txt；修复Node ESM新增API导入缺少扩展名。
- 8项浏览器合跑7通过；末项工坊因前项配置完成后无新手弹窗而超时，修正测试前置后独立1通过（7.6秒）。前7项含角色5场景、503重试取消/成功、故事停止重载；不是宣称整套浏览器全绿。
- 已查看character-c4-wide.png及character-c4-narrow.png：175模块构建通过，宽屏紧凑列表和无重复边框输入区、窄屏头像气泡无横向溢出。整体产品视觉满意度仍由玩家评价。

## 39-B请求策略接线（2026-10-19）

- `python -m unittest tests.test_provider_retry tests.test_ai_engine tests.test_model_connections tests.test_character_chat_transport -q`：28通过，1.197秒；默认关闭、次数上限、Retry-After、余额/认证/读取失败不重试、同步/异步等待取消。
- 同策略与流式回归29通过，3.252秒；174模块前端构建通过。UI进度及真实HTTP故障注入验收尚待完成。

## 39-A停止改发续验（2026-10-19）

- `npx playwright test e2e/story-stop.spec.js`：1通过，9.4秒；停止后load结果等于初始正文、新草稿保护、原请求恢复和修改重发。
- `.venv/Scripts/python.exe -m unittest tests.test_character_group_lifecycle tests.test_character_group_service tests.test_character_group_routes -q`：68通过，13.603秒。新增取消批次撤回重发、不越过后续输入；原重生成失败撤回成功批次保持兼容。
- `npx playwright test e2e/character-groups.spec.js`：5通过，36.7秒；停止修改无重复、连续发送、显示间隔、后台未读、撤回重生成、无效JSON隔离。
- 前端构建174模块通过；旧格式编辑及早停竞态待补，不声称39全部完成。

## 39-A实际接线（2026-10-19，阶段中）

- `.venv/Scripts/python.exe -m unittest tests.test_generation_routes tests.test_generation_control tests.test_streaming -q`：32通过，3.459秒。HTTP同步/流式停止、旧请求隔离、取消不落盘及故事checkpoint回退。
- `npx playwright test e2e/workshop-stop.spec.js`：1通过，8.0秒；停止恢复、已有新草稿不覆盖、编辑找回原请求、修改重发。假模型专用慢流标记避免预览过短产生时序误报，不改变生产延迟。
- `npm run build`：174模块通过，既有chunk体积警告。故事按钮仅构建验证，尚未以工坊通过替代故事/角色验收。

## 39-A第一片（2026-10-18，非完整玩家功能）

- `.venv/Scripts/python.exe -m unittest tests.test_generation_control tests.test_streaming -q`：30通过，3.621秒；build/generation-control-first.txt。
- 验证取消先到阻止提交、提交先到返回committing、跨对象/旧请求隔离、跨线程取消与退出清理、SDK流取消关闭且只调用一次。
- 尚未接真实生成入口/停止按钮/编辑恢复，目的目标继续；不当作39-A或版本节点完成。

## 40输出限制修复（2026-10-18）

- `python -m unittest tests.test_streaming tests.test_story_prompt_builder tests.test_story_settings -q`：47通过；build/output-limits-focused.txt。
- `.venv/Scripts/python.exe -m unittest discover -s tests -q`：913通过，51.806秒；build/output-limits-full.txt。
- 新用例4100推理包+4100空包+5400字逐字JSON完成一次请求，预览不含推理；字节异常/600秒总时长异常关闭请求且不重试。
- 普通/重写200、500、3000字目标均保持软篇幅提示，输出预算从接口配置独立取值12000；原工坊/故事流式事务测试保持通过。
- 初次专项仅预览断言漏掉工坊内置“结论”标题，按协议修正后全部重跑通过。无新UI、本轮无需构建新包；未使用付费请求。

## 38-B持续创作目标（2026-10-18）

- `.venv/Scripts/python.exe -m unittest discover -s tests -q`：910通过，68.938秒；build/workshop38b-python.txt。
- `node --test tests/*.test.mjs`：146通过；`npm run build`173模块成功，既有chunk警告。
- `npx playwright test e2e/other-workshop-review.spec.js e2e/workshop-review.spec.js`：5通过，32.9秒；四类新目标保存/重载，发布后三类资产继承、偏好不继承，以及原世界书流程。
- 新test_other_workshop_brief验证三个资产类型首次整理、30条历史后独立取材、手动编辑/清空保护、旧格式；偏好不采纳模型目标、不泄露未授权敏感证据；四类HTTP长度限制/持久化/存盘失败原子性/已发布只读。
- 未访问付费模型或玩家数据。39停止/重试/UI需求只写设计，未计为本轮功能。

## 38-A其他工坊审阅（2026-10-18）

- `.venv/Scripts/python.exe -m unittest discover -s tests -q`：907通过，51.365秒；build/workshop38-python.txt。
- `node --test tests/*.test.mjs`：146通过；`npm run build`173模块成功，既有chunk大小警告。
- `npx playwright test e2e/other-workshop-review.spec.js e2e/workshop-review.spec.js`：5通过，18.8秒；角色/文风/实体/偏好/世界书部分接受拒绝、重载保留、发布真实HTTP流程。
- test_other_workshop_review覆盖三资产类型存盘失败原子性、存档重读、撤销、过期ID，偏好批次撤销/冲突原子性、高影响队列和发布只读。
- 首跑因异步新手弹窗遮挡失败，改为明确等待并关闭；修正假模型将偏好工坊误分为后台分析的测试路由。最终完整重跑通过。
- 已查看build/other-workshop-review.png；原三栏与审阅列表保持，白底编辑框问题记录P2。无真实玩家数据或付费模型请求，不代表模型创作质量验收。

## dev.21包验证（2026-10-18）

- `tools/build_windows_portable.ps1 -SkipDependencyInstall`：前端、主程序、更新助手重新编译成功；自动ZIP结构/版本/隐私/覆盖保留UserData检查通过。日志build/dev21-package.txt。
- ZIP 38,411,094字节，SHA256 `0f30dc8432a8754aadd2bcf41ac69e5fa6164199c49a38b3b4b2ded8a851326c`；release_notes两项测试通过。
- 功能验收沿用下方37完成证据。本次仅版本和交付文档变化，未宣称纯净Windows实机测试。

## 工坊37最终验收（2026-10-18）

- `.venv/Scripts/python.exe -m unittest discover -s tests -q`：904项通过，54.079秒；build/workshop37-python-final.txt。
- `node --test tests/*.test.mjs`：146项通过；build/workshop37-node.txt。
- `npx playwright test e2e/workshop-review.spec.js e2e/full-player-loop.spec.js e2e/worldbook-revisions.spec.js`：24项通过，1.6分钟；build/workshop37-browser-final.txt。
- 最后修正目标首尾空白保存后显示未保存的问题，`npm run build`173模块通过，独立workshop-review场景再次通过（4.8秒，总9.1秒）。build/workshop-review-desktop.png已查看，折叠目标区和批选工具条清楚，无新增常驻大面板。
- 新增HTTP测试覆盖局内/全局同名隔离、高影响确认、保存失败及旧ID重试；新目标测试覆盖旧会话、首次模型整理、手动编辑/清空保护、30消息后独立取材、发布排除目标。浏览器覆盖重新载入及发布后新轮继承。
- 初次广泛回归加载了尚未修正的测试夹具（registry mock和测试资产重名），修正后完整重跑通过，不计为生产故障或掩盖失败。
- 不包含真实付费模型创作质量评估、干净Windows或便携包验收；本轮无发布，不改变原dev.20包。

## 工坊37审阅闭环（2026-10-17）

- `python -m unittest tests.test_workshop_review tests.test_worldbook_workshop tests.test_worldbook_workshop_agent tests.test_workshop_history tests.test_worldbook_workshop_capture tests.test_streaming -q`：44通过。
- `npm run build`：172模块成功；既有chunk大小警告。
- `npx playwright test e2e/workshop-review.spec.js`：1通过，4.5秒；完整独立建世界书→假模型真HTTP提出三项→部分接受拒绝→重新载入→发布→核对正式资产。截图build/workshop-review-desktop.png已查看。
- 初跑暴露组件事件this绑定错误，已修正并通过；两次测试夹具问题（未自行建资产、重载未关闭启动弹窗）已修。无真实玩家数据或付费请求。

## 暗流实体板块最终回归（2026-10-17）

- `.venv/Scripts/python.exe -m unittest discover -s tests -q`：894项通过，60.434秒；`build/entity-final-python.txt`。
- `node --test tests/*.test.mjs`：146项通过，701ms；`build/entity-final-node.txt`。
- `npm run build`成功171模块；保留既有chunk大小提示，不是失败。
- `npx playwright test e2e/entity-ledger.spec.js e2e/worldbook-revisions.spec.js e2e/full-player-loop.spec.js e2e/npc-identity.spec.js e2e/timed-effects.spec.js`：27项通过，1.8分钟；`build/entity-final-browser.txt`。不是全仓库所有E2E。
- 已查看`build/entity-ledger-desktop.png`，三类记录清楚、依据/知情可展开、独立车队影响仍在；记录默认折叠，无额外常驻界面。
- 要求到实现/验证映射见36完成审计表。假模型提供可控语义，检验真实HTTP和UI/存储流程；未验证真实LLM在任意题材中都遵守知情与人物动机。
- 无付费模型请求、玩家存档访问、版本升级、打包或远端操作。本轮目的板块完成，不宣称全部实体系统完成。

## 实体账本浏览器流程（2026-10-17）

`npx playwright test e2e/entity-ledger.spec.js`最终1项通过（8.7秒，场景4.5秒）。真实HTTP访问隔离假模型，覆盖计划不生成影响、行动创建影响、改名、死亡保留实体/车队、账本记录与依据可展开、撤回、重生成不重复及重新载入身份/账本一致。已查看`build/entity-ledger-desktop.png`。首跑因脚本误写“本局专属”按钮图标超时，修为真实按钮后通过。前端构建171模块成功；仅既有chunk提示。全量回归另行收集，不以此一例替代。

## 暗流分类与依据（2026-10-17）

`python -m unittest tests.test_entity_events tests.test_entity_domain tests.test_causal_ledger tests.test_request_budget -q`：38项通过（0.042秒）。新增计划不执行/不造影响、行动来源/时间/知情存取、事实不重复执行、旧协议默认与输入边界、作者认知能力资源性格摘要验证。只证明程序与提示输入行为，不以假回复证明真实模型不泄漏秘密。下一完整HTTP/浏览器及撤回/重生成验证。

## 实体生命周期（2026-10-17）

`python -m unittest tests.test_entity_domain tests.test_causal_ledger tests.test_request_budget tests.test_asset_lifecycle -q`：39项通过（0.064秒）。新增死亡保留身份/行动/计划、停止额外推演、三种来源死亡策略、取消仍保留来源、状态导出重载与恢复旧快照、停用不取消影响。

`node --test tests/entityVisibility.test.mjs`通过；`npm run build`成功170模块，既有chunk提示。只验证表单映射和编译，未宣称已视觉验收死亡说明；整块浏览器阶段继续。

## 实体账本身份关联（2026-10-17）

`python -m unittest tests.test_causal_ledger tests.test_entity_domain tests.test_asset_lifecycle tests.test_capture_lifecycle -q`：44项通过（0.269秒）。新增身份来源导出重载、改名显示更新、同名新实体不接管/误触死亡、旧卡重命名和克隆独立身份验证。尚未新增浏览器验收，生命周期完整行为继续实施。

## 实体身份基础（2026-10-17）

`python -m unittest tests.test_entity_domain tests.test_request_budget -q`：20项通过（0.040秒）。新增测试覆盖旧数据重复载入身份一致、改名保存身份不变、同名新领域实例身份不同、旧位置参数不被新字段改变。不代表资产克隆/账本身份接线/完整实体模式验收；下一完成这些接线再做HTTP/UI回归。

## 世界书闭环最终验收（2026-10-15）

- 全量Python883项通过，77.458秒，`build/worldbook-final-python.txt`。随后旧工坊归属识别和模型审计历史过滤两处补充，用19项工坊专项重新验证通过（0.138秒）；新增一项测试，不虚报884项全量重跑。
- 前端146项通过（823ms），`npm run build`成功170模块；仍有既有500KB chunk警告，非构建失败。
- `npx playwright test e2e/worldbook-revisions.spec.js e2e/full-player-loop.spec.js e2e/npc-identity.spec.js e2e/timed-effects.spec.js`：26项通过（2.2分钟）。真实HTTP连接合成假模型，覆盖新增/修改/废止/撤回/审阅和主要玩家流程，不称全仓库所有E2E。
- 已查看最终`build/worldbook-review.png`：勾选批量工具栏、即时保存反馈、候选未生效标记；弹窗内可滚动。
- 新`test_worldbook_workshop_capture`验证局内有效投影、撤回后旧草稿409且磁盘不变、旧格式工坊同样拒绝、重新打开发布成功、归属持久化。Agent测试确认审计历史不注入模型。
- 完成审计表见35。全局模板不作为捕获目标、人工内容保留、模型返回迟到不复活、源ID而非回合数字判定，分别由capture/lifecycle/revisions/review专项覆盖。
- 本轮没有真实付费模型请求、没有玩家存档访问、没有EXE或远端发布。真实AI语义质量不由固定假回复代替证明。

## 世界书界面接线（2026-10-15，最终审计继续）

- Python前一轮全量880项通过（62.424秒）；追加撤回候选与重生成测试后，review/lifecycle专项23项通过（0.698秒）。不把旧全量计数当作最新全量。
- 新增`e2e/worldbook-revisions.spec.js`：真HTTP假模型，自动新增/更新/废止/撤回以及勾选接受/全部拒绝通过，13.6秒；已查看`build/worldbook-review.png`。随后将误导的候选“已启用”改为“待审，尚未生效”，待最终构建复核。
- 审计发现局内工坊读取尚未使用回合投影，保留为当前必修项；完成后再统一终验。本轮不使用付费模型或玩家存档。

## 世界书人工审阅后端（2026-10-14）

`python -m unittest tests.test_worldbook_review tests.test_capture_revisions tests.test_worldbook_capture tests.test_capture_lifecycle tests.test_worldbook_revisions -q`：43项通过（0.384秒）。6项review测试覆盖update/retire接受及撤回、拒绝不复活、手改冲突、过期源、整批失败、后续人工修改保留；FastAPI TestClient真实路由验证读修订→接受→旧修订409→撤回后列表恢复。界面接线和浏览器仍待，不以HTTP单测替代最终UI。

## 世界书自动修订阶段2（2026-10-14）

`python -m unittest tests.test_capture_revisions tests.test_world_change_events tests.test_worldbook_capture tests.test_worldbook_revisions tests.test_capture_lifecycle -q`：45项通过。验证有源证据自动update/retire、ID保留、原文回退，人工模式及错误/缺失证据索引不自动改旧条目；保留旧恢复信号不能被误写成自动新增的回归。无真实付费请求、浏览器或整板块完成声明。

## 世界书修订阶段1（2026-10-14，板块未完成）

`python -m unittest tests.test_worldbook_revisions tests.test_capture_lifecycle tests.test_worldbook_capture tests.test_context_activation tests.test_npc_identity -q`：42项通过（0.301秒）。覆盖新增撤出、修订/失效逆序恢复、同号不同回合、人工编辑/删除保护、自动-人工-自动修改链、幂等、既有捕获并发边界，以及正式捕获→持久撤回→正文与局内资产列表→重载有效内容一致。仍需自动修订/审阅全链、真实HTTP与浏览器；本片未跑全量、未打包或付费模型。

## 故事运行一致性板块收尾（2026-10-14）

- 最终Python：`.venv/Scripts/python.exe -m unittest discover -s tests -q`，865项通过，64.591秒。初跑9个错误均因旧CausalResolution测试替身未带state_mgr，补真实StateManager后通过；未向生产流程添加替身兼容绕过。
- 前端：`node --test tests/*.test.mjs`，146项通过；`npm run build`成功（170模块），仅既有大chunk提示。
- Edge：`e2e/npc-identity.spec.js`＋`e2e/timed-effects.spec.js`三项，及`e2e/full-player-loop.spec.js`22项通过。不是全仓库所有浏览器文件全跑。身份链路包括真HTTP、流式UI、改名仅一卡、离场不被提及复活、重返ID保持、失败不落盘、重生成、重载和撤回。
- 单元补充覆盖同名冲突/未知ID/多操作冲突的整体原子性，显式在场跨回合不被“害怕死亡”词串误隐藏，不同故事ID隔离、摘要不发送无关历史人物、存取回溯元数据一致。
- 已视觉查看`build/npc-identity-desktop.png`：一张阿林卡及正确状态，无看守重复卡。测试数据为隔离合成内容，未读取玩家游玩存档。
- 本轮真实模型共4次请求，低于6次上限，均测试时关闭思考。首批`build/effect-eval-20261013-233552-857519/report.json`发现中断20秒后却写50秒并删剩余毒；补实际applied提示及禁止中断后清除/重写存续效果的约束。
- 修复后`build/effect-eval-20261013-234754-840216/report.json`：两次请求，生命0、实际20秒、毒剩3次、余时0、中断标志均通过；人工阅读正文/状态时间：昏迷非死亡、没有完成长休，此用例时间与世界后果通过。正文仍代写玩家自语/运功，不能称文学、玩家行动权或全部模型质量通过；默认思考配置问题仍保留，不擅改用户配置。
- 目标核对：持续效果有限实测✓；人物身份/改名/离场重返✓；正常/重生成请求接线✓；事务/存取/撤回✓；侧栏与真HTTP浏览器✓；设计与分类日志✓。范围不含完整实体记忆、账本重构、世界知识升级、EXE、版本升级或远端发布。

## 修复后真实复核：状态通过不代表语义通过（2026-10-13）

- 命令：`python tools/testing/evaluate_timed_effects.py --live --disable-thinking --max-requests 6`。官方DeepSeek，沿用配置模型名，六次请求合计15215 total tokens，未修改接口设置，未使用玩家内容。
- 本地合成报告：`build/effect-eval-20261013-230415-040425/report.json`。三例短等待/临界长休/不推进时间的生命、实际秒数、剩余次数、余时、中断标志均通过；用增强后的check_state对该旧报告重算亦全部通过，未再次发请求。
- 人工正文审阅：短等待只结算一次毒伤，无时间例保持状态；临界例的future reason写死亡，正文也写停止呼吸，与已载入概述“生命0昏迷”相违。整体语义验收不通过，不把自动passed:true当全部通过。
- 已修：通用提示明确后果依世界规则而非归零必死；报告改state_passed、narrative_review=pending。新增2项评估检查测试及1项正常/重生成提示组合测试。
- 专项：`python -m unittest tests.test_effect_evaluation tests.test_story_prompt_builder tests.test_effect_progress tests.test_timed_effects tests.test_ai_engine tests.test_model_response -q`，54项通过（0.435秒）。初跑测试误将旧模板世界信息限定在user消息，改为验证system＋user完整请求，不改生产布局。
- 本轮未重复全套Python/浏览器构建（上一轮855项/2 Edge仍为历史证据），未包/发行。新提示真实复测、默认思考模式输出配置问题仍待；不自动增加输出预算或无限重试。

## 持续效果真实模型抽样与修正（2026-10-13）

- 真实请求共6次，沿GameSession→生产提示词/解析/状态提交链路，隔离合成数据；开发区配置只读，不含玩家故事。模型名沿当前配置deepseek-v4-flash。
- 第一批2次：默认设置，均4096个completion token全部为reasoning，finish_reason=length且无content；不通过。使用22374 total tokens为两批合计计量，不等于费用金额。
- 第二批4次：仅验收时按官方参数关闭思考；十五秒计划为seconds/15、程序生命95，正文额外-5使最终90，发现重复delta；临界长休被绝对current拒绝。两例均不通过。脚本当时漏刷新world_premise，已修，不将缺少概述造成的场景偏差归因于正式模型质量。
- 没有发送修复后新付费请求，no_time案例未执行。真实模型质量门尚未通过；`--disable-thinking`测试覆盖也不等同当前默认配置通过。
- 回归：新增5项（4项效果＋1项长度失败）。专项73项通过（1.433秒），完整Python855项通过（54.128秒），Edge持续效果2项通过（13.9秒）。本轮无前端代码变动，未重复构建/截图或全部浏览器套件。
- 验收工具：`python tools/testing/evaluate_timed_effects.py`默认只列案例，不收费。显式`--live --cases short critical --max-requests 4 --disable-thinking`才发请求；每次执行的上限独立，重复执行仍产生费用。报告保存在独立build/effect-eval-*；本轮报告时间后缀195015-333350与195217-785823，仅本地，不提交。
- 修复边界：缺少独立事件依据的追加delta会拒绝且保持存档；完全相同current回显无副作用。新增原因字段不能证明AI给出的理由真实，不把格式校验等同语义正确。

## 持续效果故事接线（2026-10-13）

- Python：`.venv/Scripts/python.exe -m unittest discover -s tests -q`，850项通过，70.806秒；新增`tests/test_effect_progress.py`15项，专项47项通过。
- 前端：`node --test tests/*.test.mjs`，146项通过；`npm run build`170模块成功，仍有原有大chunk体积提示。
- 浏览器新增：`npx playwright test e2e/timed-effects.spec.js`，Edge两项通过（16.9秒）。真实应用HTTP＋流式正文＋隔离假模型，覆盖初建效果不追溯扣血、15秒余时、重生成不双扣、失败不保存、跳月到期、重载存档与撤回恢复、生命归零在20秒中断长休。
- 既有玩家流程：`npx playwright test e2e/full-player-loop.spec.js`，22项通过（1.6分钟），包含资产载入、并发、工坊、生图、日志、更新及反馈；与新增场景合计24项，不是全体浏览器文件全跑。
- 已人工查看自动截图`build/timed-effects-desktop.png`及`build/timed-effects-critical.png`：侧栏75/100且效果消失、0/100且剩30秒与程序报告一致；未见本次状态标签溢出。截图是本地测试产物，不提交玩家内容。
- 没有调用真实付费模型、读取玩家游玩档、构建EXE或发布GitHub。假模型回显实际状态/报告而非自行计算结果；不据此声称模型语义/文学质量验收通过。

## 持续效果纯计算切片（2026-10-13）

- `.venv/Scripts/python.exe -m unittest tests.test_timed_effects tests.test_settlement_contract tests.test_npc_presence tests.test_causal_resolution tests.test_story_prompt_builder -q`：46项通过（0.278秒）。其中10项新测试见test_timed_effects。
- 新覆盖：五轮到期、两轮后余三轮、大跨度有限效果不重复伤害、显式零阈值阻止后续治疗、零轮/非法参数、副本无污染、接续不双扣、新buff不追溯、旧创建tick语义、状态快照恢复。
- 未做真实HTTP、浏览器、模型付费测试、打包或发布；当前模型调用未接新预结算能力，不把计算测试当完整跳时体验通过。

## 22y-A纯压缩规划复用（2026-10-10）

- `python -m unittest tests.test_compaction_plan tests.test_story_memory tests.test_request_budget tests.test_story_events tests.test_story_continuity tests.test_story_prompt_builder -q`：44/44（0.242秒），含6项新测试。空/单单元、等于水位、force下限、完整前缀/近期、bridge边界、输入深拷贝及故事适配回归。
- 通过git show读取HEAD提取前`_plan`并AST单独执行，固定种子22生成1000组长度/成本/预算，普通＋force共2000次与新函数输出对照全部一致；无落盘旧代码或玩家文件操作。
- 首次16项中1失败是新测试预期错误：首单元900已满足归档量，只归档该单元；修正预期后通过，未扩写核心兜底。纯后端小提取，无UI/模型/协议/持久格式变化，未重复全量浏览器、构建、打包或线上发布。

## GitHub发布（2026-10-09）

- 用户明确授权发布并完成新电脑gh登录；公开`Lzy44567/AliveWorld`已发布预发行`v1.6.0-dev.19`，包含分类更新说明、标准名称ZIP及SHA256附件。先草稿上传核对，再转公开；最终isDraft=false/isPrerelease=true，两附件state=uploaded。
- ZIP 37933194字节，GitHub服务端digest与本地c5b-preview一致：`9acc4e5a7e0ad913f27ba4ea67f0bdf056533f8b75dd34d3262d0d8e37a80901`。标准命名满足当前自动更新附件匹配；未声称已经实测玩家自动更新。
- 未推送开发源码。发行标签指向公开仓库既有main `87fa595c9dcfa029d1da2682017034e5485d1d8d`，不是当前私下构建源码；附件代码来源为e765f63，后续946e2d5仅改文档。不得将Release自动生成的Source code视为本次EXE源码。
- 发布页：https://github.com/Lzy44567/AliveWorld/releases/tag/v1.6.0-dev.19 。旧版本附件保留，未更改仓库可见性或迁移仓库。

## 角色阶段设计边界核对（2026-10-09）

- 当前代码e765f63：`python -m unittest tests.test_character_memory_m2 tests.test_character_cognition_m3 tests.test_character_capacity tests.test_character_ooc_c3 tests.test_character_proactive_contact tests.test_character_proactive_service tests.test_character_proactive_schedule -q`，103/103（19.709秒）。本轮为阶段专项复核，不将以前819/145/Edge7冒称新运行。
- `Get-FileHash`复核现有c5b-preview ZIP为`9acc4e5a7e0ad913f27ba4ea67f0bdf056533f8b75dd34d3262d0d8e37a80901`，与构建记录一致。仅修文档，不重复构建/打包、付费调用、真实迁移、EXE启动或线上发布。

## C5-B批量管理/每日免打扰（2026-10-09）

- 全Python：`python -m unittest discover -s tests -q`，819/819（55.717秒）；新增跨午夜/白天、关闭/非法时段、结束后完整idle、计划跨时段取消、批量部分冲突/未来会话不授权、静态批量API/保存回归。
- 全Node：`node --test tests/*.test.mjs`，145/145（899.819ms）；批量只提交明确所选会话、逐项结果、不自动重试回归。
- 最终构建169模块通过（1.60秒），JS `index-BWmqKmVG.js`，已有>500kB警告保留。
- 最终Edge：`npx playwright test e2e/character-proactive.spec.js e2e/character-groups.spec.js --reporter=line`，7/7（42.8秒），含真实勾选/批开批关/旧格式禁选、新会话默认关、每日免打扰保存及C4/C5-A回归。wide/narrow截图已视觉检查。
- 首次浏览器结果4通过/1失败/2未运行，发现设置对象刷新覆盖刚输入的分钟；已改字段级同步并重新构建后7项全部通过，未把初次结果宣称成功。开发测试时UTC时间夹具/插入位置问题已修，不增加核心兜底。
- 无付费调用、真实玩家迁移或线上发布；浏览器工程链路不是角色质量/冻结桌面启动证明。
- 本地打包脚本`-SkipDependencyInstall -SkipFrontendBuild -ArchiveSuffix c5b-preview`完成（exit0），主程序/更新助手编译及结构、隐私、覆盖升级保留数据校验通过。ZIP：`release/AliveWorld-1.6.0-dev.19-windows-x64-c5b-preview.zip`，SHA256 `9acc4e5a7e0ad913f27ba4ea67f0bdf056533f8b75dd34d3262d0d8e37a80901`。旧包保留、内部VERSION仍dev.19；未实际启动冻结EXE，既有可选voice_helpers/numpy/Android警告保留。

## C5-A当前会话闭环（2026-10-09）

- 最终全Python：`python -m unittest discover -s tests -q`，813/813，55.148秒。涵盖授权、0/1/N一次规划、真实无input组/账本/撤回、编辑租约、新输入取消、重启、最后额度争抢、API设置及私密运输；早期整合84项曾因并行修改中的测试状态失败，最终全量已通过。
- 全Node：`node --test tests/*.test.mjs`，144/144，871.7103ms；生产构建168模块，1.66秒，既有大chunk警告保留。
- Edge：`npx playwright test e2e/character-proactive.spec.js e2e/character-groups.spec.js --reporter=line`，6/6，41.9秒。真实UI授权→正式输入→无input主动组→撤回/暂停、编辑节流、旧会话不迁移，以及现有多气泡回归。wide/narrow截图已由主代理检查。
- 隔离假模型与20倍调度时钟仅在E2E启动器；无真实API费用/玩家文件操作。此浏览器验收不等于EXE桌面启动或角色文学质量通过。
- 本地包：现有脚本加`-SkipDependencyInstall -SkipFrontendBuild -ArchiveSuffix c5-preview`完成，主程序/更新助手编译及结构、隐私、覆盖升级保留数据校验通过（exit0）。`release/AliveWorld-1.6.0-dev.19-windows-x64-c5-preview.zip`，SHA256 `27389a0392b1804ece0d7db4f4bc26a4963cacb923240e566540deca1b7871cf`。保留旧包，内部dev.19不冒升线上版本；本轮未启动EXE或发布GitHub，可选voice_helpers/numpy/Android警告保留。

## 请求检查分离（2026-10-09）

- `python -m unittest tests.test_character_group_lifecycle tests.test_character_group_service tests.test_character_group_routes -q`：63/63（12.874秒）。send/batch/retry原检查移动到专用请求模块，字段/错误/幂等/业务规则不变。
- 本次没有界面/协议/格式变化，未重复全量浏览器、构建和打包；旧785/137/43证据不伪装成新运行。主动联系仍设计中，不作为此次测试完成声明。

## C4收尾 / 独立备份事务（2026-10-09）

- `python -m unittest tests.test_character_group_upgrade -q`：11/11（0.320秒）。精确原字节、同revision异hash拒绝、pending拒绝、重复升级不写、独立备份不入枚举、旧版本拒写、备份fsync失败、转换失败、临时fsync失败、replace失败、备份重名不覆盖/不删除、替换前外部编辑保护及未知/删除格式有回归。
- 最终完整Python785/785（43.418秒）；完整Node137/137（841.6176ms）；165模块生产构建通过（1.75秒），产物JS仍`index-DeWWrL-M.js`，既有>500kB警告保留。
- 只临时测试调用备份函数，没有生产API/UI接线或真实记录升级。无付费调用；此前43 Edge为同一UI/运行代码的C4验收历史，本轮没有重跑，不冒称新的迁移UI或包启动证据。
- `powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_windows_portable.ps1 -SkipDependencyInstall -ArchiveSuffix c4-preview`完成，exit0；主程序/更新助手编译及ZIP结构、隐私排除、覆盖后UserData保留校验通过。包为`release/AliveWorld-1.6.0-dev.19-windows-x64-c4-preview.zip`，SHA256 `28176a0013fe256549a1b91d216f59eefdd0db0a8c9c66128ca8ce1867a8f192`。旧dev.19ZIP保留，内部VERSION仍dev.19，后缀仅隔离本地验收产物，不是线上版本升级。
- 本轮未自动启动EXE，不将编译/归档校验当作冻结桌面运行通过。PyInstaller的可选voice_helpers/numpy、Android以及隐藏模块警告保留；没有为无关可选能力安装依赖。独立升级模块无生产引用，不作为包中已开放功能宣称。

## C4-V /新建入口启用（2026-10-09）

- 10月8日固定产物全量进程句柄在恢复时已不存在。实际解析`build/e2e-report/index.html`内report.json：total42/expected42/unexpected0/flaky0/skipped0；C4组3、旧角色17、全流程22。`.last-run.json`也为passed。没有将缺失句柄猜为成功。
- 随后新UI明确schema2，并在创建后接通独立订阅。旧`character-mode`夹具显式重写创建1，失响应自定义route也明确1；单独`character-groups`真实UI默认测试不改请求，比较旧格式记录前后相等。
- 入口相关6/6（1.1分钟）及137 Node（832.8412ms）通过，165模块重建（1.68秒）通过；新增旧记录比较后的最终43 Edge全部通过（384891.446ms / 6.4分钟）。`build/e2e-c4-final.json`实际stats为expected43/skipped0/unexpected0/flaky0；4 C4+17旧角色+22全流程，固定构建期间未改运行代码，无自动重试掩盖。
- Python774/774为本片后端/假供应商最终证据，入口启用仅改前端/测试，无新的Python源码改变。真实迁移文件事务尚未封装执行，不把纯迁移测试称备份失败/实际替换验收。

## C4-C3真实气泡界面验收进度（2026-10-08）

- 修复后最终窄验收：137 Node/137（846.9907ms），165模块build（1.68秒），C4 Edge3/3（25.1秒）。完整初跑42项为40通过/1已读竞争失败/1未运行（6.7分钟），不得当作完整V通过；下一在固定重建产物上重跑全量。

- 新增独立`character-groups.spec.js`三项真实Edge/HTTP/后台服务场景：首次专项3/3（29.9秒）；1600x1000/390x844截图已检查，无横向溢出。真实DOM句柄在预览转正式后仍connected，不只比较文本。连发甲乙被第二次正常请求一次认领。
- 间隔首气泡立即正式、离开后第二气泡送达/未读、重开零预览、整批重生成撤回、坏最终JSON仅保留正式用户输入；旧schema1夹具独立保留。
- 初次完整42项运行发现快速撤回与read ACK的REVISION_CONFLICT；本次修复后新增确定性状态回归。另补在途旧GET不能清终态预览测试。首次专项结果不是修复后最终build/V证明；完整验收须重新构建并重跑。
- 完整Python774/774（44.541秒）通过，新增2项C4假回复格式测试；没有真实玩家记录/付费模型。当前构建165模块通过，既有>500kB提醒保留；无EXE/版本/迁移/远程操作。

## C4-C2客户端会话状态（2026-10-08）

- `node --test tests/*.test.mjs`：135/135，813.1792ms。新增characterGroupStore10项；旧characterChat44项保留。
- 覆盖切换/隐藏仅detach、后台正式恢复不自动读、两个预留气泡原位确认不重复、忙碌连发/下批显示快照、input_saved只清除对应双草稿、丢响应同动作核对零重发、失败不回填正式输入、预览不ack、前台正式ack不覆写新修订、整组分页去重与旧页重核、显式重试保留新草稿/legacy busy拒绝、version2逻辑组容量。
- 仅合成API/状态；没有本片Python、真实浏览器或打包证据。旧772 Python属于B8，125 Node构建属于C1。下一真实UI与完整V，未启用新UI创建或玩家迁移。

## C4-B5b旧执行与后台服务兼容（2026-10-08）

- 新增12项旧execution/service与2项新C4真实连接预算测试；专项35/35（7.799秒），最终完整Python735/735（38.217秒）通过。先前732项结果发生在最终预算修复之前，不作为最终证据。
- 验证V1/V2×LEGACY/M3/C3六组合、严格快照/执行身份、pending非正式、失败/取消/中断重试、旧ID保持、重复token零额外调用、调用前取消零调用、启动零自动收费、保存失败无成功广播、旧重生成失败保留及成功原子逆账/替换、来源高光通知、批撤回和下一正常v3。
- Astra只读审阅相关30项，发现P1真实连接预算被忽略；新旧服务均改用config.budget_options。真实配置形状测试验证自定义24000窗口/1234输出预留传入供应商报告；新旧tiny窗口皆零调用。
- 仅隔离临时仓库和假供应商；没有玩家记录、付费请求、生产/API/UI激活或版本/包/远程操作。本片没有新Node/构建/Edge证据，不以旧UI成绩证明新气泡界面完成。仍需API/public view、C前端及完整V/迁移确认门。

## C4-B5a旧协议上下文/容量准备（2026-10-08）

- 新增7项旧上下文与3项逻辑组容量测试，专项10/10（0.013秒）；旧M3/C3及C4上下文相关60/60（3.760秒），最终完整Python721/721（33.641秒）通过。
- 严格验证六种V1/V2×LEGACY/M3/C3装配组合、旧缺可选协议字段默认、协议/OOC冲突不重解释、原user/ai ID保持、真实多气泡history不合并/重复、未回应队列隔离、旧regenerate排除原输入/AI、整组预算裁剪且原输入不截断。纯上下文无服务调用或玩家写入。
- schema2 capacity显式version2、formal_groups按逻辑保留组而非气泡计数；失败档案只耗action/attempt；原capacity_report仍拒schema2，未来格式拒入新reader，私人ledger数量不公开。
- Astra新增22v第13节后主代理全文读取；尚未实现legacy_execution validator、显式重试/提交事务及service分派，不能把721项称旧重试可执行或C4闭环。API/生产/UI未切换，无新增Node/build/Edge/EXE证据；这些层的旧成绩仍仅历史。

## C4-B4后台调度（2026-10-08收尾，隔离服务）

- 新增21项服务级Python；主代理专项21/21（5.805秒），Astra最终复核专项21/21。中断后原全量process handle已不存在，未把其推测为成功；10月8日重新实际运行完整Python711/711（37.491秒）通过。
- 覆盖同次组请求/多气泡实时预览、正式确认、不自动续话、X/Y合并下一请求、无订阅gaps、未读单调、失败预览不保存/不自动收费、取消显式retry与token幂等、设置下批生效、四槽及第五输入先保存未领取、生成中断、有效尾批恢复、订阅异常、保存失败无成功广播、服务层整批重生成/撤回、私人ledger/候选不入事件。
- Astra复现的两项竞争已修：cancel后立即retry/send不先wait_idle仍能启动新worker；启动恢复尾批后旧队列不产生新请求，恢复期间新输入才授权继续。启动不调用模型、失败/取消不自动重试均由假transport调用次数严格断言。
- 送达保存失败保留已验证候选和正式前缀，阻止继续写入；新服务启动重新排短间隔恢复，零新增provider调用，不重播正式前缀。公开stream状态只含轻量游标/计数，不重复整段历史/私人账本。
- 本片仅新增隔离schema2服务与测试，生产构造/路由/默认创建未切换；旧attempt执行兼容和API/UI尚未接线，没有新Node/build/Edge/EXE证据，不挪用B3构建称当前多气泡界面可用。无真实玩家数据读写、付费调用或远程操作。

## C4-B3多输入上下文（2026-10-07，隔离实现）

- 新增12项Python专项12/12（0.095秒）；最终完整Python690/690（29.173秒）通过。覆盖独立输入/OOC关联、未来及截止前未领取队列隔离、完整组历史与旧场外不重放、重生成逆账/旧回答排除、第二条输入来源/高光、世界书关键词与偏好、超过20组的精确seq原文召回及预算裁剪后证据收缩、当前输入不可截断、旧格式/epoch/协议拒绝。
- Astra只读核对相关74项通过、未发现阻断P1；其建议的队列分批及召回/预算组合覆盖已补充到12项主代理专项中。没有真实玩家文件访问、格式切换或付费调用。
- Node116/116通过，卡片实体可见性脚本通过；前端160模块构建通过，原有>500kB单包警告保留。新C4四切片均按角色类别可达且顺序严格验收，旧切片身份保留。
- 本片没有新Edge/Playwright或EXE验收；现有生产服务/UI尚未使用新上下文，不将690项后端/注册表回归冒称完整多气泡聊天已可用。下一为真实后台调度/旧attempt兼容，再前端与全量浏览器。

## C4-B隔离存储/纯事务基础（2026-10-07，尚未生产接线）

- 新增29项Python（5项纯迁移/格式与24项消息组事务），专项29/29（2.908秒）；最后完整Python678/678（29.168秒）通过。此前674项回归发现repository默认validator过早绑定，导致3项故障注入测试不能覆盖读写校验；已改为默认动态校验，原故障测试与完整回归重新通过，未放松未知格式保护。
- 覆盖三态原子/逐条提交、候选不作来源/未读、批末账本、气泡间插话顺序、X/Y独立输入/OOC与一次认领、取消显式继续、失败大队列有界前缀、CAS/动作与timer幂等、保存失败无半批、epoch拒迟到、重启中断/短间隔重排、已读单调、批撤回/重生成/重试与满容量替换。
- Astra只读审阅的具体缺陷均补回归：A→玩家X→B不能撤回/重生成旧批；失败/取消重试成功后仍可整批撤回；失败重生成后可撤回原批；满正式组容量可重生成重试。候选ledger_plan来源/权限/注解/目标、reservedID及反向身份严格校验，损坏候选不恢复。
- 合成旧多次重生成/撤回/归档/OOC、pending/retry协议及ID保持；转换纯内存、原文件字节/mtime不变，未知格式拒绝；默认生产仓库仍schema1，新格式只显式注入临时测试目录。
- 本片未接服务调度/实际C4上下文/前端；没有新增Node/Edge/构建/EXE证据，不能用纯函数结果称后台聊天已完整可用。678项包含旧系统回归；没有付费模型调用或玩家数据访问，真实模型角色质量未评估。

## C4-A多气泡解析/实时传输（2026-10-06，未启用真实会话）

- 10项新协议/lexer测试+2项真实SDK假HTTP测试；专项35/35（2.978秒），全Python649/649（26.060秒）。同次调用逐字符chunk跨转义/代理对任意切割，第一与后续气泡均可在完整JSON前产生预览；只有根messages数组直接子对象text公开。
- 拒绝未知/重复字段、坏类型/ID/顺序、7气泡、8001码点、原始字节/深度超限、孤立代理、非有限数与截断。来源仅映射身份字段、不改文本、不接收未生成气泡引用。预览不代替完整账本/注解验证。
- SDK只请求一次、零自动重试，日志不带正文；v1/v2预览及默认协议不变。尚未接组持久化/输入队列/UI，未读取或迁移真实数据。无本片新Node/Edge/build/包验收，不挪用此前成绩称完整C4成功。

## C4-0角色接话指导（2026-10-06，独立源码小片）

- Astra额度中断未留文件，重试后完成22t，主代理全文读取；只实施独立短指导，不落多消息候选schema/间隔或输入队列。
- 新增7项Python装配验收：四个M3/C3 core准确一次、旧legacy不变、显式core覆盖保留、两模式/两输出协议的输入/来源投影不变、必需预算、不接受新输出字段、static前缀不随玩家输入变化。窄测7/7，最终完整Python637/637（23.641秒）；此前基线630/630（23.517秒）也通过。
- 全部Node116/116、entityVisibility通过；160模块构建通过，JS541.51KB，既有500KB警告保留P2。前端未变，这些检查在后端指导编辑前运行，仍覆盖相同前端文件。
- 编辑后真实Edge专项C3/M3 2/2通过（23.6秒/39.7秒，总1.1分钟），覆盖双输入来源/重试/重生成与旧原文召回/修订/撤回/小屏。本轮没有重新运行全量39项浏览器，也没有新增UI视觉效果；旧39/39仅为C3历史结果。
- 全部隔离合成数据/假供应商，无付费模型和玩家数据读取；只能证明指导接入及现有边界不变，不能证明自然度/伴侣感。无版本、包或远程变化，多气泡/未读新机制尚未实现。

## C3结构化场外提示与单步角色自主（2026-10-06，源码片）

- 新增23项Python C3领域/事务/路由测试及1项假供应商协议测试；完整Python630/630两次通过，最终23.250秒。窄测109/109、其它角色相关77/77通过。覆盖Unicode1000/1001/非法型、旧无OOC指纹/空值等价、非空说明幂等差异、严格请求白名单、v1/v2输出、C3/M3/legacy独立身份和覆盖、必需预算超限零调用、OOC-only零调用。
- 来源验证覆盖C3保留4条/4000字符召回及最终证据闭包、场外词不触发世界书/记忆/原文召回、伪造ID与仅场外引文失败、下一轮无场外历史/证据、公开来源端点不带说明。pending/retry/正式/archived与owning C3身份不符拒写；未知版本磁盘load/恢复不改hash/mtime、不调用模型。
- 事务覆盖流式/非流式、偏好授权重检、原双输入重试、取消先赢/提交先赢、服务端重启interrupted恢复、重生成失败保留/成功归档、撤回隔离及保存失败无半轮。独立Astra只读审阅未发现未处理P0/P1；审阅不代替运行测试。
- 新增7项Node双输入测试，最终全部Node116/116通过；原始草稿快照与规范化payload分别保留，成功双框一起条件清空、任一新编辑均保护、切会话/失败/重载/undo成对恢复、纯场外/超限不请求、重生成/重试不发送新草稿。真实提示词注册断言36片、新旧顺序及唯一可达，不放松为任意数量。
- 可见性检查与最终160模块生产构建通过；541.51KB主bundle既有超过500KB警告仍P2，未隐藏。C3 Edge专项1/1（23.3秒）及首轮完整Edge39/39（5.4分钟）通过无skip；最终构建再次完整Edge39/39（5.3分钟）通过，C3最终路径23.5秒。最新宽窄截图再次视觉检查。
- 浏览器创建合成角色/对话，验小框在台词框上方、OOC Enter换行零请求、OOC-only禁发、收起附带提醒、正式双输入/合法账本、原说明再生/失败重试、新草稿保护、下一轮排除、末轮撤回双输入回填、重载历史折叠说明。宽1600x1000/窄520x900截图已检查，无横向溢出，小框/发送可达。
- 全部使用隔离临时目录/build/e2e-runtime和假供应商，无玩家私聊读取或付费模型调用。初始窄测修正fixture断言/UTF-8 surrogate表达及旧无OOCretry身份兼容，未通过放宽OOC权限解决。工程验收不证明真实角色主动性、自然语言蕴含或模型改写OOC的语义隔离；没有心理分析/持久控制/C4/C5、版本提升/打包/远程发布。

## M3局内认知与有界来源召回（2026-10-06，源码片）

- Python新增25项，最终完整606/606通过（24.226秒）；覆盖公开索引白名单/作者与推测身份、当前正式源/引文/权限、合法修订链及循环/对象变更、无链接/零词法命中/近期重合不召回、4完整消息/4000 Unicode字符边界、两源整组/共享去重/初选稳定顺序/单调不回填/父项与history闭包、最终实际输入与allowed消息集合、非法旧dialogue_event/伪造源/未投影修订目标、预算失败零调用。
- 新attempt独立context版本、旧缺字段与启动中断/显式重试、reply.v1/v2兼容、未知版本真实临时磁盘load/API409/begin/recovery零调用且hash/mtime不变、旧提示词覆盖隔离、来源修订→撤回恢复、取消零调用和保存失败原子性通过。索引GET拒绝query/body并no-store，不写索引或原文副本。首次全量新夹具使用了错误error_code字段和不存在update方法，修正为真实error.code/save后重跑，未放宽运行契约。
- 前端新增7项，全部Node109/109、角色57/57通过：当前公开ledger/revision归属、来源/对象筛选、投影白名单、同revision迟到淘汰/删除、修订不一致最多一次重新核对且非轮询、草稿保留、SSE与非流式报告归属/重载清空。真实提示词注册可达检查提升到28片并验证新旧身份准确顺序；检查脚本已纳入独立认知测试。
- tools/run_checks.ps1通过；最终共享源顺序修复后完整Python606及全Node109再验通过。可见性与158模块生产构建通过，537.38KB主bundle警告保留P2，不隐藏。没有升级公开版本、扩容量、打包或远程动作。
- M3真实Edge专项1/1（43.4秒），初次完整Edge38/38（5.3分钟）通过；最终代码再次完整Edge38/38（5.3分钟）通过无skip，M3最终路径42.3秒。实际创建/旧话题超过20轮/来源与对象筛选/查看关联原文/保留纠正草稿/模型实际recalled_sources/旧用户源合法supersede/撤回恢复/重载无假报告覆盖；新增当前来源链接也纳入最终浏览器路径。首次专项在小屏重载后点击隐藏左栏超时，恢复宽屏再选会话后通过，未修改产品逻辑迁就脚本。
- 宽1600x1000及窄520x900最新character-m3-wide.png/character-m3-narrow.png已再次视觉检查，面板可滚动无横向溢出。全部使用隔离build/e2e-runtime与临时目录、假供应商，无玩家数据/付费调用。工程验证不证明真实模型对限定语/心理/陪伴体验的语义质量；本片不是详细心理侧写、语义搜索或无限长期记忆。

## M4a容量诊断（2026-10-05，源码片）

- 新增10项Python专项：80%整数阈值/等于上限、公开计数与操作门独立、内部维度合并无私有文本、UTF-8规范化体积/仅一次整会话序列化、只读hash/mtime/修订不变、额外query/body拒绝、未来/坏文件不修补、failed attempt同revision重新读取、requests2048/attempts4096发送/撤回/重生成/显式retry零provider调用、512正式回合只禁新增但仍可合法重生成/撤回、active128空ops仍能提交而非空超限整轮失败、撤回归档新增操作且不清理旧账本。首次夹具误用不存在的service.generate，修为实际execute；未修改运行契约以迁就测试。
- 前端新增3项，角色Node50/50、所有Node102/102通过：容量投影白名单/类型/计数状态/已知阻塞一致性，同revision迟到响应淘汰，跨会话/删除/网络失败及草稿保留。读取失败清除旧报告并显示未知，不伪造0/normal。
- tools/run_checks.ps1通过，最终完整Python581/581（24.228秒）、可见性、155模块生产构建通过；527.35KB主bundle警告仍P2，无隐藏或假定已优化。
- 真浏览器M4a专项1/1（9.7秒），完整Edge37/37（5.1分钟）通过无skip。正式创建0→发送1的服务端容量、临界提醒直达说明、折叠技术记录、网络故障未知、宽窄无溢出验证；near压力由隔离路由注入合成投影，仅测试UI，不声称真实小会话已满。
- character-capacity-wide.png（1600x1000）及character-capacity-narrow.png（520x900）已视觉检查。只读接口Cache-Control:no-store，客户端不以revision缓存、不轮询/每token刷新、不改硬限额。全部隔离合成存储/假模型，无付费或玩家私聊读取，无版本/包/远程变化；本片不证明扩容、无限记忆或真实心理语义效果。

## M2自动重要记忆与高光（2026-10-05，源码片）

- 后端新增18项（16项M2领域/API/事务、1项真实SDK v2流式预览、1项fake显式协议标记）；完整Python571/571，补充窄测69/69、此前整链97/97通过。主代理再次运行tools/run_checks.ps1成功，覆盖Python、前端分组、可见性及构建。
- 覆盖严格v1/v2三字段、索引布尔/越界/重复、未知版本零调用、pending协议冻结/旧读不迁移、注解来源/speaker/v2 origin/inverse绑定、16自动优先与8手动独立、去重/私有投影、取消链继承、ACK幂等/撤回水位不倒退、损坏通知/保存失败/取消/重生成无假通知。
- 角色Node47/47，全部Node99/99与可见性检查通过；新增7项自动记忆投影/通知持久去重/跨会话归属/丢设置响应/丢ACK核对后有界补写等。首次全量提示词导航仍认旧19片，已更新为准确22片及独立v2-v1顺序，保留唯一可达/稳定顺序检查，重跑99/99通过。npm无通用test脚本，使用node --test tests/*.test.mjs与项目检查脚本，未将不存在脚本当验收。
- 153模块生产构建通过，522.13KB主bundle警告保留P2。M2 Edge专项1/1（21.5秒），完整Edge36/36（5.2分钟）无skip通过；取消连接期间出现Windows asyncio10054提示，对应取消/重试用例与最终套件通过，不据此宣称连接永不异常。
- 浏览器真UI验证：明确边界注解→公开原因/关联原文→取消/重载/恢复→独立手动重要→纠正保留未发送草稿→重生成无新提示→撤回移除自动项。character-m2-wide.png（1600x1000）和character-m2-narrow.png（520x900）已视觉检查，面板可滚动无横向溢出。
- 全部使用隔离合成会话/虚假供应商，无付费或玩家私聊读取；只证明协议/事务/UI，不证明真实模型注解语义、心理准确性或陪伴感。未升版本/打包/发布；22p只是下一容量诊断合同，C3/C4/C5尚未实现。

## C1/C2/M1本地验收包（2026-10-05）

- 再验Python553/Node90/可见性/151模块构建与完整Edge35（3.8分钟）通过。Windows主EXE/更新助手真实编译，便携包结构、版本、排除配置/玩家数据/日志/开发目录、覆盖保留UserData通过。
- 实际EXE PYZ包含14个character模块，memory/preferences/world_context均在，项目tests模块不在；嵌入前端JS哈希一致，ZIP内README/INSTALL_WINDOWS/USER_GUIDE均与源码哈希一致。首次文档检查发现README和安装说明复制早于文本更新，已重新封包后逐个验准。
- PackageOnly会读到陈旧LASTEXITCODE，虽然PowerShell验证通过仍可能误报失败；去掉这处不适用的原生退出码判断，成功完成时明确归零。实际以继承LASTEXITCODE=1跑PackageOnly通过；ArchiveSuffix含../被参数白名单在构建前拒绝。启动器/发布说明7项回归通过。
- 版本选择无答复，未提升公开VERSION或覆盖原dev.19；独立文件`AliveWorld-1.6.0-dev.19-windows-x64-M1-20261005.zip` SHA256=`08f697eff346e85f68c88b717d3b90337e60ce066e5918b927b665aeef576b02`。旧包hash仍954d4b91ee6d1ce82307bf3c344986a7a44be5703ed5d885e6275f8341e5dc4b，原dist本地UserData由脚本备份保留且不进入ZIP。包/日志未提交Git，无远程发布。
- 真实桌面窗口启动、外部电脑与真实模型扮演质量未由本次自动测试验证；程序内显示dev.19是保留版本的结果，不是本包漏打新代码。

## M1有来源记忆（2026-10-05，源码片）

- 记忆专项10项：中英文/NFKC/完整英文词/单位上限、超过20回合与32候选、保护优先/32条8意图、私有/无正式来源过滤、预算整条省略与最终报告/证据一致、非法链/循环、设置严格校验、8根限额/取消/幂等/CAS/原子写失败、来源/supersede/撤回/失败重生成/失效释放、busy/跨会话/私有/未知版本、旧引文不扩张新经历证据。路由新增严格白名单/设值/重载/来源投影验收；合成夹具的save修订需正确递增，未放松CAS。
- 角色Node27项、全量Node90项通过：报告/原文投影白名单、纠正保留草稿、设值响应归属、丢响应核对不重发。完整Python553/553、可见性和151模块生产构建通过；513.83KB主bundle警告保留P2，不通过隐藏警告解决。
- Edge M1专项1/1（48.4秒）通过：真实UI标记/来源/草稿、34个中间正式回合、旧来源离开20回合窗口后保护取材、服务端重载、公开说明和取消。宽1600x1000/窄520x900截图已检查，资料可滚动，无横向溢出。首次全量因旧标题断言“共同经历”失败，真实标题改为“共同经历与记忆”；更新断言后完整Edge35/35通过（3.8分钟），无跳过。报告默认折叠，展开后使用资料面板滚动。
- 隔离合成存储、虚假模型，未读玩家私聊、无付费调用、未改dev.19 ZIP。验证只证明请求和事务/界面，不证明自然语言总结蕴含、纠错语义成功或真实陪伴感。

## C2角色偏好只读接入（2026-10-05，源码片）

- 偏好专项10项及角色路由8项合计18通过：缺省/严格设置、人工确认/自动active过滤、敏感与类别、整条Unicode/去重/限额、关闭零读取、只读加载、预算/证据不扩权、CAS/忙碌/重载、当前请求冻结、撤销后显式重试、幂等和重生成。
- Node新增2项，角色专项24通过：设置响应归属发起会话、切换隔离、修订传递、失败保留服务端状态、忙碌拒绝更新。首次预算测试夹具恰好2400字符却期待尾项仍放入，已修正为能验证“大项不放入但小项仍可完整放入”的场景，不改运行上限。
- `tools/run_checks.ps1` Python542/542、Node87/87、可见性检查和149模块生产构建通过。Edge专项1/1（13.0秒）及完整34/34（3.0分钟）通过：真实UI默认不发送、普通/敏感独立授权、流式及非流式拼装、服务端重载保留、关闭撤销授权/零拼接。新测试使用自己的合成角色和偏好，结束删除合成偏好，避免污染后续用例。
- `character-preferences-wide.png`（1600x1000）和`character-preferences-narrow.png`（520x900）已视觉检查，开关和权限说明可读，小屏资料面板可滚动；设置响应前复位原开关，失败不会留下虚假的已启用状态。
- 隔离合成数据、零付费调用、不读取玩家聊天。不能把请求拼装测试当作真实扮演质量；dev.19ZIP SHA256仍954d4b91ee6d1ce82307bf3c344986a7a44be5703ed5d885e6275f8341e5dc4b。既有500KB bundle体积警告保留P2，未隐藏。此片未打包或发布GitHub。

## C1角色世界书连续性（2026-10-04，源码片）

- 新增`test_character_world_context.py`9项：本次/近期双方正式消息排序、四回合/12000字符整消息上限、私有/归档/开场/示例/账本排除、停用/待确认/待删除/常驻/绝对规则、Unicode关键词与16条上限、预算整条裁剪同步安全报告、无世界书、流式/非流式报告和撤回/重生成、必需超限零调用。与假供应商专项合计20项通过。
- Node新增3项：安全报告白名单/类型/长度、跨会话与迟到事件隔离、非流式结果/详情重载/新请求清除。角色store专项22项通过；首次测试用了原始对象而非Vue管理对象导致身份保护拒绝，修正夹具后通过，未放宽运行身份校验。
- `tools/run_checks.ps1` Python531/531、Node85/85、可见性检查和148模块生产构建通过。浏览器专项1/1（13.4秒）：AI正式回复提出场景词，玩家下一输入未复述仍命中条目，流式及非流式报告/重载不假造报告。初次缺串行前置角色、随后非流式错误要求预览，已修正专项夹具。
- 完整Playwright/Edge33/33（3.0分钟）通过；最后仅补充新请求后重新展开报告的截图断言，专项1/1（13.4秒）通过。`character-world-report-wide.png`（1600x1000）与`character-world-report-narrow.png`（520x900）已视觉检查：条目来源/计划可读，窄屏资料面板覆盖显示，无报告文字溢出。
- 隔离合成夹具、零付费调用，不读玩家私聊。测试证明取材/来源/预算/事务，不证明角色知道一切世界秘密或文学质量；不重打dev.19包，不远程发布。生产bundle超过500KB的既有体积警告仍列P2，未通过隐藏警告冒充优化。

## dev.19：A/B1/B2合并验收（2026-10-04）

- `tests/test_character_fields_editing.py`新增11项：结构CAS/旧页面拒绝、AI白名单/完整字段保留、非法后项无半草稿、保存失败回滚、双工坊/手动编辑冲突、目标replace失败、回执二次保存失败与不重写恢复、外部变化冲突、同目标写入门、旧工坊修订有条件兼容。
- Node新增3项：显式默认分配、Unicode限额不截断/未知字段版本拒绝、兼容描述排除作者开场；`tools/run_checks.ps1` Python522/522、Node82/82、可见性检查、146模块构建通过；最终静默Python重跑522/522。
- 完整Playwright/Edge第一轮33/33（3.1分钟）通过；B2专项23.1秒通过，原生启用预览/取消/采用/保存、示例进入新会话请求、既有快照/原始导入隔离、工坊独立修改/降级/发布。宽窄编辑截图已视觉检查。克隆后刷新修订并验证未保存示例写到副本、原卡不变；最终完整33/33（3.4分钟）通过。
- 中间一次完整验收32/33：世界包测试在故事列表先更新、导入弹窗后关闭的间隙误认为操作已结束，重开被随后关闭覆盖。增加可观察的弹窗关闭完成条件后整轮通过，不改运行代码、不延长超时掩盖问题。
- 全部隔离合成资产与假供应商，无玩家数据读取或付费模型调用。自动化不证明真实模型的扮演、语义理解和心理质量，不宣称长期记忆已经上线。
- Windows主程序与更新助手已真实构建；最终ZIP版本/结构/私密排除/UserData覆盖保留检查通过，hash/归档一致性如下。未把归档验证冒充冻结桌面启动验收，实际桌面启动和真实API由玩家验收；保留dev.18ZIP、不发布GitHub。

### 最终包交付记录

- ZIP：`release/AliveWorld-1.6.0-dev.19-windows-x64.zip`；SHA256 `954d4b91ee6d1ce82307bf3c344986a7a44be5703ed5d885e6275f8341e5dc4b`。
- 最终脚本结构/版本/隐私/UserData覆盖保留验证通过，主EXE及更新助手均重新编译。嵌入VERSION为dev.19，嵌入前端与最终生产构建逐文件hash相同；归档含character_asset_write/character_profiles/asset_workshop，不含tests/tools.testing模块。
- 分类发布说明由既有release_notes.py抽取本版日志，首次缺标题v前缀已纠正并重新生成；未发布到远程。

## 角色预设开场B1（2026-10-04，源码更新）

- `tests/test_character_opening.py`11/11：空/缺失/空白、8000Unicode边界与非法型/字段/版本、旧文件hash不变、重复创建/原开场ID、资产已删除仍先查幂等/墓碑、save与transaction冻结、独立请求投影、首轮撤回/重生成、伪造四类来源、必需预算超限零调用和完整示例裁剪安全元数据。
- Node新增3项：有效结构卡显式开场源/不猜旧文本或source、响应丢失冻结payload和ID/不同草稿拒绝/显式同请求重试、忙碌不重复与确定性失败释放。`tools/run_checks.ps1`通过Python511/511、Node79/79、可见性检查及144模块构建；另外静默全量Python复跑511/511。
- B1浏览器专项1/1（13.1秒）与完整Playwright/Edge33/33（3.0分钟）通过。真实前端主动复制、覆盖取消、大屏展开、成功落盘后丢响应、同ID重试、零回合/零未读、首轮上下文、重生成/撤回/重载、小屏无横向溢出均验证。宽窄截图`build/e2e-results/character-opening-wide.png`和`character-opening-narrow.png`已视觉检查。
- 全部使用隔离合成资产/会话与假供应商，无付费调用或玩家数据读取。测试证明投影/引用校验和生命周期，不证明自然语言蕴含、真实模型角色质量；不是B2示例编辑验收。创建待确认只在本次store保留，应用彻底重载后须先核对列表。版本与EXE包未变，没有GitHub动作。

## 角色通讯式交互A（2026-10-04，源码更新）

- `tools/run_checks.ps1`：Python500/500、Node76/76、可见性检查、141模块生产构建通过。Node新增6项：Enter/Shift/Ctrl/Command/IME/229/repeat、独立设置重载/删除、坏JSON/未知版本/配额、2000条容量、在途delivery不变及模式更新失败/同会话发送删除互斥。
- 角色浏览器专项10/10通过（1.5分钟），保留既有9项；追加输入IME与Shift换行不请求、Enter一次发送、长文本Ctrl发送、流式位置/实际非流式调用、模式解释及真实模型路由参数、每会话重载、小屏无横向溢出。截图`build/e2e-results/character-chat-ux-wide.png`与`character-chat-ux-narrow.png`已视觉检查。
- 完整旧浏览器回归待最终记录；仅隔离合成数据与假供应商，零付费调用。未重打包/改dev.18ZIP，不宣称开场或示例编辑已经实现。
- 最终完整Playwright/Edge32/32通过（3.0分钟），含全部既有故事/工坊/角色/日志/更新验收；修改旧下拉选择断言为radio/开关真实操作，没有删除对应模式、非流式或重载断言。源码交付不改变现有dev.18包，真实性格质量未在本轮评测。

## dev.18角色卡I1（2026-10-04）

- 初步全量：Python498/498、Node70/70、可见性与138模块构建；Playwright/Edge31/31通过（2.9分钟），外部卡导入→分项预览→模型白名单→转换编辑→新旧会话重载均通过。宽屏`build/e2e-results/character-i1-profile.png`已视觉检查，旧宽/窄角色用例仍保留。
- 后续新增两项Python检验后，I1专项14/14通过：包括两角色×两形态×两表现×六场景共48份请求资料，工坊标签保存和撤销后发布保留结构。新增工坊浏览器发布路径后将再次全量验证；不把前一次31项当作此追加路径的通过证据。
- 合成假供应商、隔离资产与会话；零付费调用，未读取玩家私聊。角色质量、真实API及桌面EXE启动仍需玩家验收。自动压缩角色记忆尚未接入，不宣称无限长期记忆。
- 最终`tools/run_checks.ps1`：Python500/500、Node70/70、可见性检查、138模块生产构建通过；工坊追加路径浏览器专项1/1通过。第一次专项因测试服务器读取尚未重建的静态bundle而找不到新testid，重建后通过，并在最终全量中复验。
- 实际Windows主EXE与更新助手构建通过，ZIP38,142,164字节；`test_windows_portable_package.ps1`验证版本/结构/私密排除/UserData覆盖保留通过。SHA256：`19fef8466d90b7bfc6b83126949222d5a30b09f0d4ee3427640e7bef9a0211b7`。实际EXE归档含`core.character_profiles`、`utils.atomic_yaml`及角色模块，无tests/tools.testing；嵌入前端JS与本次生产构建hash相同，嵌入VERSION为dev.18。发布简介由现有release_notes.py从分类更新日志抽取，仅保留本版内容。
- 未重复尝试此前被执行策略拒绝的桌面自动启动，不把归档验证称为冻结运行smoke。旧dev.17ZIP保留，新包不含用户配置/会话或合成质量夹具；没有push/tag/GitHub Release。
- 最终完整Playwright/Edge31/31通过（3.2分钟），包括追加工坊结构转自由文本发布/原source保留；不是只跑角色专项。主EXE/更新助手构建与前端测试并行，使用同一已完成生产bundle，无运行源码在此期间变化。

## 角色会话侧栏UX-S1（2026-10-03，源码更新）

- tools/run_checks.ps1通过：Python486/486、Node70/70、可见性检查、137模块构建；完整Playwright/Edge30/30，保留原29项。最终小屏焦点调整另跑侧栏专项，不将旧构建当作新焦点证据。
- 新增后端2项：summary字段白名单、正式时间与Unicode160字符、旧默认兼容、撤回末条、52会话分页；新增Node7项：搜索/排序、读水位/撤回重生成、置顶持久化、坏数据/未知版本/配额、2000条容量、分页失败/重复游标/40页上限/迟到刷新、隐藏页面与迟到剧透。
- 新浏览器用例覆盖同卡双会话、搜索/置顶重载、后台完成未读/呈现清点、资料/共同经历/设置、剧透关闭、宽窄栏互斥；截图build/e2e-results/character-sidebars-wide.png与character-sidebars-narrow.png已视觉检查。小屏关闭列表后焦点返回入口另有断言。
- 全部隔离合成数据/假供应商，零付费模型调用；不验证真实文学/人设质量。没有构建WindowsEXE或更新已有dev.17ZIP。
- 最终补验：焦点回入口断言Playwright1/1通过，坏偏好降级调整后Node7/7再次通过，最终137模块构建通过。全量30项跑于焦点小修之前，最后修改由上述专项覆盖。

## 角色卡片选择/世界书可见入口（2026-10-03，源码修复）

- Node63/63、角色路由/生命周期Python27/27、135模块生产构建通过；完整Playwright/Edge29/29，2.5分钟，保留既有28项。
- 新用例验证角色不再是SELECT、无结果搜索反馈、名称搜索选卡、世界书卡片选择、规则实际进入character.reply请求、重载后资料显示绑定名称。`build/e2e-results/character-world-binding.png`已视觉检查。
- 复用共享CharacterAssetCard的选择模式；原资产管理模式仍经旧浏览器用例验证。只使用隔离合成数据，无付费API；未重构后端世界书/会话协议，未重新构建EXE或覆盖dev.17ZIP。

## dev.17最简角色闭环验收（2026-10-03）

- `tools/run_checks.ps1`：Python484/484、Node63/63、可见性检查、134模块生产构建通过。角色专项53/53（含既有存储11与提示词9）；新增生命周期/词法22、API5、真实SDK传输6。
- 完整`npm run test:e2e`：Playwright/Edge28/28，2.2分钟。保留原22项，新增6项角色UI：选卡创建、双表现、真实预览先于提交、可见性/来源、并发切换隔离、重载、坏JSON保留、停止/重试、重生成/撤回、小屏入口。截图`build/e2e-results/character-wide.png`及`character-narrow.png`已视觉检查。
- 针对真SDK的合成传输测试覆盖同一stop chunk的content、仅一次调用、取消及trace零私聊正文；假模型11/11。旧导航测试更新为真实新增的三角色切片，未删除原顺序、可达性和草稿保护断言。
- 故障覆盖pending写失败零调用、提交失败无半回合、终态写失败只读、重启恢复、迟到attempt隔离、设置快照、来源伪造、未知字段、私有可见性、预算超限及容量。假服务不证明真实供应商/文学/人格质量。
- 最终本地包真实构建成功；ZIP37,695,842字节，版本/私密文件排除/覆盖保留UserData检查通过，SHA256为`d4aa66c6d34fcf366b5eb7f8ce1715958eb37509b430d4b28a3b66b1dc86e7a9`。实际EXE嵌入归档含11个角色模块，无tests/tools.testing模块。
- 自动启动EXE的命令被本机执行策略拒绝，因此冻结桌面运行smoke未完成，不以归档检查冒充启动通过。桌面启动/真实API/扮演质量交用户验收。本轮不调用付费API，不访问玩家存档，不发布GitHub。

## 角色R1A-1存储基础（2026-10-03）

- `.venv/Scripts/python.exe -m unittest tests.test_character_chat_repository -v`：11/11；快照/模型投影、幂等创建、冻结底稿、CAS并发、replace失败、墓碑、防损坏覆盖、未来schema、路径/限额及双会话隔离。
- `.venv/Scripts/python.exe -m unittest discover -s tests -q`：446/446（原435项+新11项）。仅合成与临时数据，无付费调用。
- 本片未改前端，未运行新的浏览器验收；HTTP/模型/流式角色UI、动作账本与重启pending恢复不是本片已验收内容。

## 故事/工坊流式验收（2026-10-03）

- `tests/test_streaming.py`：22项；JSON可见字段逐chunk抽取、转义/emoji、嵌套键、choice0/工具调用/finish异常、128KiB/4096chunk限额、单次调用、三工坊事务、故事保存前锁、断流继续与慢消费者。
- `aliveworld-ui/tests/streaming.test.mjs`：15项；UTF8/CRLF/SSE解析、无终态/坏事件、不自动重发、六类接口及旧JSON路径、上下文预览隔离。纳入一键检查，连同原专项35项共50项。
- 一键检查通过Python435/435、可见性检查、Node50/50与130模块构建；完整Playwright/Edge22/22（1.5分钟）。首个正文回合验证真实预览先出现且状态未提交，上游stream标识/一次结算；工坊验证真实预览，并保留跨对象/跨模式/失败/重载回归。
- fake_openai_app真正发出分块SSE，仅测试隔离合成数据。不宣称真实供应商支持、文学/角色质量或测得首字性能提升。首版断网不取消已启动服务器事务，EOF无complete须重新载入核对，无自动收费重试。

## F1/U1验收（2026-10-02）

- 前端：`cd aliveworld-ui; node --test tests/feedbackOperation.test.mjs tests/promptNavigation.test.mjs`，35/35通过；现已纳入`tools/run_checks.ps1`。四动作过期重试/卸载、错误/剪贴板/秘密扫描、分类顺序与注册并集、草稿失败/并发/认证/锁定均有确定性测试。
- 后端：`.venv/Scripts/python.exe -m unittest tests.test_feedback_diagnostics tests.test_prompt_studio tests.test_story_prompt_builder tests.test_settlement_prompt_sections -q`，34/34通过。初始命令误写不存在模块已纠正，不是产品失败。
- 一键检查：Python412/412、可见性检查、Node35/35、生产构建129模块通过。完整`npm run test:e2e`：Playwright/Edge22/22通过（1.4分钟）。原提示词注入断言未删除；补齐真实dialog取消/确认、模式空态/只读/覆盖版本、401稿件可选复制、父级guard与反馈新快照/失败/fallback。
- 无付费模型或真实GitHub提交；窗口/剪贴板在浏览器测试中拦截。Node控制Promise覆盖过期导出和卸载零副作用，不将其写成真实远程服务或人工发送证据。

面向玩家的逐步操作请优先阅读 [MANUAL_TEST_GUIDE.md](MANUAL_TEST_GUIDE.md)。本文件保留自动测试与夹具的技术说明。

## 提示词架构整阶段验收（2026-09-24）

- `tests/test_request_budget.py`验证发送前超限阻断、输出预留、usage不可得/零值区别、连接预算校验与客户端更新、暗流固定规则及结算后状态投影、诊断隐私边界。
- 浏览器全流程验证接口预算保存、开发者切片覆盖状态，以及暗流请求中的结算后状态和资料分层；与既有并发、重掷、撤回、重载和资产启停用例一起运行。
- 本次结果：Python 389/389、前端行为检查、生产构建126模块、Playwright/Edge 22/22通过。真实模型文学质量和实际缓存收益不由假模型测试证明，发行前另按设计文档21的评测表采样。
- 预算是估算守门，不是精确tokenizer或全局自动裁剪器。历史压缩与检索选材仍归原模块；超限时保留原文并说明来源，不静默删改已装配内容。

## 目录职责

W1b（2026-09-25）：`tests/test_capture_lifecycle.py`覆盖存盘后调度、存盘/调度失败、正常/重掷源回合身份、模型等待期间撤回与编辑/删除、过期修订零调用、原子写入失败和四类局内资产导入。测试用线程事件精确控制竞态；不依赖真实LLM延迟。该验收不等于已提交世界书变更的历史回溯。

W1a（2026-09-24）：`tests/test_world_change_events.py`覆盖通用信号、证据逐字匹配、无效字段、临时变化待确认、旧输出兼容和GameSession调度；提示词构建测试验证开关和独立切片。最终Python 398项、前端行为检查/生产构建与浏览器22项通过。该语料指定模型输出以测试程序契约，不是实际模型的语义识别成绩。

| 目录/文件 | 用途 | 是否推送 |
| --- | --- | --- |
| `tests/` | 后端自动测试、测试夹具 | 是 |
| `aliveworld-ui/tests/` | 前端纯逻辑测试 | 是 |
| `aliveworld-ui/e2e/` | 玩家界面端到端验收 | 是 |
| `tests/fakes/` | 隔离假模型服务 | 是 |
| `tools/run_checks.ps1` | 一键自动检查 | 是 |
| `tests/fixtures/manual_assets/` | 可安装的手动验收卡 | 是 |
| `data/` | 用户个人资产、存档、测试安装副本；`*.template.yml` 是可推送模板 | 普通资产否；模板是 |

## 一键自动检查

在仓库根目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_checks.ps1
```

它会优先使用仓库 `.venv\Scripts\python.exe`（不存在时才使用系统 `python`），并运行 Python 单元测试、前端可见性测试和前端生产构建。这样迁移电脑或系统 Python 版本后，不会误用缺少项目依赖的解释器。网络、真实 API 和真实模型不在自动检查范围内。

## Windows 发布候选与自动发布

开发者可在仓库根目录双击 `release_windows.bat`，或在 PowerShell 中执行：

```powershell
.\tools\release_windows.ps1
```

默认流程会要求 Git 工作区干净，自动运行上述检查、完整 Playwright 验收、Windows 双 EXE 构建、便携包校验，并从 `CHANGELOG.md` 精确生成当前 `VERSION` 的发布说明；它不会上传网络。只检查版本、日志和工作区时使用：

```powershell
.\tools\release_windows.ps1 -PreflightOnly
```

确认提交已经位于 `origin/main` 且 GitHub CLI 已登录后，才可显式执行：

```powershell
.\tools\release_windows.ps1 -PackageOnly -Publish
```

`-Publish` 会创建与 `VERSION` 同名的 tag/Release；开发、alpha、beta 和 rc 版本自动标为 pre-release。脚本不会自动强推、改写 main 或覆盖同名 Release。

## C4 C1 客户端订阅/显示偏好基础（2026-10-08）

新增 `characterGroupClient.test.mjs` 9 项；全部 Node125项通过（722.462毫秒），此前相关专项58项通过。覆盖同一订阅多组/多气泡UTF8拆字、严格ready/连接序号/实际请求身份、坏JSON/EOF/字节上限不重发、等待帧时Abort仅取消reader、错误安全化、未知事件/心跳、JSON组命令、旧偏好无写入映射、两个互斥开关/全关与无逐字选项、损坏/未来设置原文保留。

旧get()/delivery设置API形状保留；新JSON/subscribe方法独立加入，不改变旧fetch-POST行为。当前store/UI尚未消费新方法，不能声称已可见或C4完整。前端构建成功（Vite保留既有>500kB chunk体积提醒），无EXE/玩家迁移/付费调用/远程发布；Python本片未改，沿用B8最终772项证据，不冒称重跑。

## C4 B8 HTTP/订阅与应用接线（2026-10-08）

新增 `tests.test_character_group_routes` 15 项（路由9、订阅5、显示参数1）。与旧路由合跑24项通过（6.071秒）；容量/来源协议/新路由专项50项通过（8.309秒）。最终完整 Python 772 项通过（44.194秒）。

覆盖快速JSON（供应商仍等待时返回）、明确新格式创建/格式指纹冲突、旧默认协议、源文件字节不因GET/list改变、整组分页/撤回/删除幂等、辅助管理、单调read、重试幂等及指定旧request、共享main运行时、多进程/未startup保护。订阅覆盖实际ASGI响应/断连后worker继续、ready先发/owner与连接序号、晚订阅不重播私有预览、64帧及256KiB溢出只detach、不泄漏候选/账本计划。

首轮全量发现并修复了旧reader不支持schema2却被新投影误当支持的只读回归；真实ASGI就绪等待由2秒改为事件门10秒以容纳整套测试负载，不取消断连不影响生成的断言。模型接口管理测试显式注入空临时角色runtime，避免新lifespan扫描玩家目录。Astra本片复核被额度中断，没有审阅结论。前端仍待C片，不能用HTTP绿色测试证明界面/EXE完成；无付费模型、玩家迁移或远程发布。

## C4 B7 共享并发与生命周期基础（2026-10-08）

`python -m unittest tests.test_character_runtime -q`：11 项通过（1.041 秒）。完整 Python 757 项通过（38.697 秒）。覆盖新旧共享四槽、第五请求排队/旧抢占拒绝、槽交接前后取消无泄漏、启动前/关闭后拒绝、多进程不启动新格式恢复、lifespan同loop、旧恢复不误写schema2、关机中断旧生成与未执行预约并归还额度。Astra发现并修复等槽retry/worker尚未开始regen关闭时仍pending的缺口；新增回归及保存失败仍归还其余额度的测试。

runtime/lifespan工厂尚未接生产main/HTTP；下一片统一接线，避免两套并发额度。该测试不是前端或EXE验收，无付费调用或玩家文件迁移。

## C4 B6 公共视图与辅助操作验收（2026-10-08）

新增公共视图专项 10 项及批末记忆通知回归 1 项；全量 Python 测试 746 项通过（37.542 秒）。验证已交付前缀、整组分页、正式消息与未读摘要、排队行动的实际请求归属、旧失败请求隔离、撤回控制请求身份、忙碌时通知确认及记忆来源。Astra 复核发现的行动/请求身份混用已修复并补测试。

这一证据只覆盖后台与公共投影，不代表新 HTTP/SSE、前端多气泡界面或便携包完成；下一片按 22v 第 14 节接共享并发额度与应用生命周期。未调用付费模型、迁移玩家文件或发布版本。

## 玩家界面端到端验收

首次使用需要在前端目录安装开发依赖；之后执行：

```powershell
cd .\aliveworld-ui
npm run test:e2e
```

这不是只调用后端接口的测试。Playwright 会启动真实 AliveWorld 前后端并操作 Edge 页面，完成以下闭环：

1. 从玩家界面创建角色卡、世界书及条目、文风卡、实体卡和故事线。
2. 从右侧资产库逐项载入，并在正文输入框发送行动。
3. 由隔离假模型返回确定性正文，同时检查它实际收到的世界书、角色、文风和 Overseer 实体上下文。
4. 从玩家界面关闭资产，再次发送行动，确认被关闭内容不再进入模型请求。
5. 检查“显示高级设置”默认关闭，开启后高级分组出现，再关闭后隐藏。
6. 重试最后一回合并撤回，检查正文、模型请求和持久化状态一致。
7. 修改世界书工坊草稿，确认发布前正式资产不变，发布后重进同步。
8. 由隔离假 ComfyUI 固定制造一次执行失败，随后从正文失败卡重试并收到测试图片。
9. 重载页面并重新唤醒故事，确认正文、局内角色/文风、图片任务和当前故事状态仍存在。
10. 在两个故事之间切换并制造先后完成与单边失败，确认响应和错误只写回发起故事。
11. 在两个工坊对象之间切换，并让正文与工坊重叠运行，确认草稿、消息和任务状态彼此隔离。
12. 发布工坊后刷新整个页面，确认对话从磁盘恢复为只读历史；提示词覆盖与恢复也通过真实设置界面执行。

`full-player-loop.spec.js` 是一条从空测试目录逐步建立资产、故事和后续状态的串行验收链。完整执行或按文件执行会自动具备前置数据；直接用 `--grep` 单独运行依赖后续数据的用例时，需先运行它依赖的创建场景，否则“找不到测试资产/故事”不代表产品回归。

测试数据只写入仓库内的 `build/e2e-runtime/`，不会读取、迁移或修改源码游玩数据和便携版 `UserData/`。失败截图、追踪和报告位于 `build/e2e-results/` 与 `build/e2e-report/`。假模型不会产生真实 API 费用，也不能替代便携包、真实供应商和真实 ComfyUI 的少量人工抽查。

## 安装手动验收卡

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\install_test_assets.ps1
```

脚本只复制 `测试_*.yml` 到本机 `data/`，默认不覆盖同名文件；需要覆盖时使用 `-Force`。这些副本被 Git 忽略。

## 人工验收顺序

每次测试请新建一个名称含“测试”的存档，并只载入当前用例需要的卡，避免提示词互相干扰。

| 用例 | 载入资产 | 玩家输入 | 预期 |
| --- | --- | --- | --- |
| 世界书常驻/触发 | `测试_世界书回声` | `世界书测试` | 正文出现“世界书就绪” |
| 文风卡 | `测试_文风回声` | `文风测试` | 正文末尾出现“文风就绪” |
| 角色卡 | `测试员_角色卡` | `角色卡测试` | 正文出现“角色卡就绪” |
| 暗流实体 | `测试_暗流回声`，勾选实体名称、动机和气泡 | `实体测试` | 调试消息/本局实体显示“实体就绪”相关暗流；若模型返回空动作，记录为模型遵循度问题 |
| 资产关闭 | 分别载入世界书、文风、角色卡、实体后，在本局开关中设为“已封存” | 新建/读取干净测试存档后输入对应测试词 | 不出现该资产的“就绪”标记；实体不进入下一回合 Overseer |
| 实体可见性 | 任意本局实体 | 分别勾选名称、动机、编辑、气泡 | 本局卡、编辑入口和气泡只显示被勾选的内容；“实体：全部”一键全选 |
| 基础回归 | 任意世界 | 正常行动、重掷、撤回、存档、读取 | 随机未来、状态栏、聊天记录和存档流程保持可用 |

真实模型有不确定性：标记词用于快速暴露“世界书/文风/角色卡是否注入提示词”，不是要求模型在所有供应商上绝对遵从的单元测试。若失败，请记录使用的模型、输入、完整调试消息和存档名，以便按提交定位。

## “常识改变”题材专项验收

“常识改变”是指主角能改写群体伦理、观念、规则和公序良俗的特定故事题材，不是给所有故事开放任意改写世界的权限。这个题材会频繁产生稳定规则的新增、替换与恢复，因此适合作为世界书自动写入的压力测试。请直接新建不载入世界书的测试故事，确认系统自动生成“本局自动设定”且没有污染全局资产。

1. 在自动生成的本局世界书加入条目“公众通常认为裸体需要遮蔽”，开启世界书捕获；测试自动新增时可关闭二次确认，测试修改与恢复时保持二次确认可见。
2. 输入 `常识改变：所有人都认为公开裸体是正常礼仪`。正文明确表现能力已影响群体后，应新增规则或对同主题旧规则生成“修改”提案，不能同时保留互相冲突的两条现行常识。
3. 接受修改前，旧规则继续启用；接受后，新内容沿用原条目身份，触发词和标签能够让之后涉及衣着、公共场所或礼仪的场景召回它。
4. 输入 `常识恢复：公众裸体礼仪`。如果改变规则是后来新增的，应生成“废止”提案；如果它替换了已有规则，应提出恢复旧内容。确认前不能直接删除当前世界观。
5. 只输入“我希望大家不介意裸体”、角色撒谎称常识已经改变，或讨论一部“常识改变”漫画：如果正文没有确认能力生效，不应写入世界书，也不应仅因出现题材名称强制请求捕获。
6. 连续进行两次不同主题的改变，再分别恢复其中一次：只能定位和变更对应条目，不能按名称相似批量删除其他设定。

日志中应能区分新增、修改、废止三类提案。若模型提出修改或废止但没有给出可精确匹配的原条目 ID，系统必须拒绝自动变更正式世界书。
# 2026-10-17 dev.20 便携包交付验证

- `tools/build_windows_portable.ps1 -SkipDependencyInstall`：前端、主程序、更新助手构建成功；自动包结构/版本/隐私/覆盖升级保留数据检查通过。
- ZIP：38,408,595 字节；SHA256 `3a28495c1d0c085bc0a2b951736acf5dc53b78f7445e4746ab931813785a5c5a`。日志 `build/dev20-package.txt`。
- 本次只修改版本和交付文档，沿用本阶段894 Python、146前端、27相关浏览器场景验收；未宣称干净Windows实机或完整真实模型验收。

