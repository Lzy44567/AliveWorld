# 🚀 AliveWorld V2.0 - 商业化沙盘与自由流引擎蓝图

## 一、 项目愿景 (Core Vision)
打造一款高自由度、高容错、UI 与逻辑彻底解耦的 **AI 动态推演沙盘引擎**。
全面对标并超越 SillyTavern（酒馆）的自由度，以“暗流引擎”、“双轨推演”和“动态数值体系”作为核心差异化竞争力，最终打包为免环境配置的独立客户端游戏。

## 二、 核心技术栈选型 (Tech Stack)
*   **后端 (Game Engine)**：`Python 3.10+` + `FastAPI`。原生异步，负责引擎运算、API 提供、WebSocket 实时推送。
*   **前端 (Game Client)**：`Vue 3` (或 React) + `Tauri`。构建极速、美观的跨平台桌面端 `.exe`。
*   **数据存储**：
    *   `SQLite`：替代本地文件，管理复杂关系（存档、世界书、实体、历史切片）。
    *   `ChromaDB / FAISS`：(远期) 轻量级本地向量数据库，用于世界书与长期记忆的语义检索 (RAG)。
*   **多模态 (未来接入)**：本地部署的 `ComfyUI / Stable Diffusion API`。

## 三、 核心引擎模块 (Core Engine Modules)
1. **DM 双轨推演体系 (Dual-Track Resolution)**
   * 发散(AI) -> 物理裁定(Python掷骰) -> 具现化结算(AI)。彻底打破“顺从玩家”的降智套路。
2. **万物皆动态的键值对引擎 (Dynamic Key-Value System)**
   * AI 以严格 JSON 格式动态接管属性。新增/删除状态条（如理智、快感、护甲）、动态施加 Buff、同步 NPC 雷达。
3. **超强抗幻觉打捞防线 (Salvage Engine)**
   * 引擎内建正则表达式与偏移量抓取算法。免疫大模型发神经（把小说写在 JSON 外）、免疫审查截断、免疫空指针，强制抠出文本并保持游戏流运转。
4. **暗流统御引擎 (Undercurrent / Overseer)**
   * 挂载于“世界时间线 (World Ticks)”的独立后台运算逻辑。
   * 独立推演【非玩家实体】（世界意志、大反派、重要NPC）的阴谋与生灭。
   * 形成《因果账本 (Shadow Ledger)》，在未来玩家触发对应场景时爆发。

## 四、 展现层与客户端特性 (Frontend & UI Features)
1. **视觉驱动开发 (UI First Mockup)**
   * 先行搭建含有所有功能坑位的空壳 UI，固化产品灵感。
2. **全局绝对热插拔 (Hot-Swappable Context)**
   * 游戏中途无缝拉出侧边栏：随时切换/编辑【文风卡】、【世界书】。
   * 支持从图鉴拖拽【新 NPC 实体】介入当前场景，即插即用。
3. **沉浸式动态生图 (Dynamic CG)**
   * *(长线规划)* AI 根据当前情境 + 衣服破损状态，调用 SD 生成差分立绘，甚至通过脚本后台合成为微动态 GIF 播放。

## 五、 执行路线图 (Execution Roadmap)

### 🟢 阶段一：API 契约设计与 UI 先行 (API & Mockup Phase)
*   定义前后端交互的 RESTful API 格式（如 `/api/game/action`）。
*   脱离后端，纯手写前端“空壳 UI”，实现多 Tab 切换、侧边抽屉热插拔、对话流排版，作为灵感备忘录。

### 🟡 阶段二：后端引擎 API 化重构 (Backend API-fication)
*   搭建 FastAPI 框架。
*   将 V1.0 的 `GameSession`、`Undercurrent` 纯净化，剥离 UI 代码。
*   对接 SQLite，实现 API 接口的真实逻辑处理。

### 🔵 阶段三：全栈联调与异步多模态 (Integration & Evolution)
*   前后端对接，打通 WebSocket 实现后台暗流事件弹窗。
*   完善世界书的自动推理生成机制。
*   介入生图 API 队列。