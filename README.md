# AliveWorld

AliveWorld是一款以“动态未来、暗流实体、因果账本和可演化世界书”为核心的AI故事游戏。

当前版本仍属于开发测试版。玩家需要自行准备OpenAI兼容的文本模型API。

## Windows快速开始

1. 安装 [Python 3.12](https://www.python.org/downloads/) 和 [Node.js 20 LTS或更高版本](https://nodejs.org/)。
2. 双击 `install_windows.bat`。
3. 编辑安装脚本生成的 `config.yml`，填写自己的API配置。
4. 双击 `start_dev.bat`。
5. 浏览器访问 `http://127.0.0.1:5173`。

完整说明见 [Windows安装指南](docs/INSTALL_WINDOWS.md)。

## 开发验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
cd aliveworld-ui
npm run build
```

## 私人数据与Git

以下内容默认不会提交到Git：

- `config.yml`与API Key；
- `data/`内个人角色卡、世界书、文风、实体、存档；
- 世界书工坊草稿、语义模型与向量缓存；
- 日志、`.venv`、`node_modules`和前端构建产物。

仓库只跟踪目录占位符和以 `.template.yml` 结尾的模板资产。

## 发行计划

源码版通过项目内`.venv`降低安装门槛。未来GitHub Release/Steam版本会把Python运行时和前端静态文件打包为便携应用，玩家无需预装开发环境。详见 [发行与打包方向](docs/DISTRIBUTION.md)。
