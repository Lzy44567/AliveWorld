# 📖 AliveWorld : AI 动态推演引擎开发总纲 (v4.5)

## 一、 项目愿景 (Core Vision)
打造高容错、高解耦的硬核 AI 文字推演沙盘。
全面推行**“防御性编程”**与**“子系统独立”**，确保 AI 的幻觉绝不影响底层数值的稳定运行。

## 二、 核心架构 (Current Architecture)
1. **模块化矩阵：** 
   - `app.py`：主循环与路由控制器 (Event Loop)
   - `engine.py`：AI 思考大脑与强容错解析器 (Robust Parser)
   - `utils.py`：状态更新与文件总线
   - `ui_tavern.py`：大厅与卡片编辑器视图
   - `sys_logger.py`：**[New]** 独立解耦的日志侦听与可视化终端。

## 三、 待办任务池 (Backlog & Roadmap)

### 🔴 紧急修复与底层加固 (High Priority)
- [x] **UI 夹心饼干剿灭 (Q1)：** 重构 Streamlit 渲染事件流，按钮永远保持在流末尾，且生成期防触碰。
- [x] **独立系统日志 (Q2)：** 引入 `sys_logger.py`，实现多模块独立发报、UI端单向读取的功能。
- [x] **正则铁壁防御：** 针对 AI 忘写 JSON 格式或混杂文本的幻觉，引入 Regex 强制括号提取算法。

### 🟡 体验提升与交互改造 (Medium Priority)
- [ ] **卡片画廊化：** 抛弃下拉选框，采用卡片式列表 (Gallery) 展示角色与世界书。
- [ ] **模态编辑弹窗：** 引入 `st.dialog`，支持在不中断跑团的情况下实时编辑设定卡。

### 🔵 核心功能深度扩展 (Major Features)
1. **多层级推演树 (N × n)：** 重构 DM，生成 N 个大方向 -> 每个方向 n 种变数 -> Python 裁定 -> 投骰。
2. **多模态动态立绘：** 调用本地生图模型生成差分图，脚本合成为 GIF。