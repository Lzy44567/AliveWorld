# AliveWorld Windows 安装指南

> 无需安装 Python/Node 的 Windows 便携版已进入 dev.9 人工验收阶段，尚未作为稳定 Release 发布。源码 ZIP 仍不是傻瓜安装包。

## dev.9 便携版测试

1. 完整解压版本化 ZIP 到可写目录，建议放在非系统盘；不要只把 EXE 单独拿出来。
2. 双击 `AliveWorld.exe`。启动页会依次显示加载游戏核心、启动本地服务和打开世界。
3. 个人配置、存档、资产、图片与日志都位于 EXE 同目录的 `UserData/`。
4. 更新时关闭游戏，替换程序文件，保留原来的 `UserData/`。测试版之间升级前仍建议备份该目录。
5. 便携包已包含 Python 解释器、Python 依赖和前端生产文件；玩家不需要安装 Python 或 Node.js。文本模型 API 和可选 ComfyUI 仍由玩家自行配置。

## 当前源码版需要什么

- Windows 10/11 64位。
- Python 3.12。
- Node.js 20或更高版本。
- 一个OpenAI兼容的文本模型API。

首次安装需要联网。AliveWorld不会提供或共享API Key；每位玩家必须使用自己的配置。

## 推荐安装步骤

1. 下载或克隆AliveWorld源码。
2. 双击根目录的 `install_windows.bat`。
3. 安装脚本会在AliveWorld目录内建立 `.venv`，安装Python依赖和前端依赖。
4. 基础安装不会安装 PyTorch。仅在需要本地语义检索时，另行双击 `install_semantic_windows.bat`。
5. 打开 `config.yml`，填写自己的 `api_key`、`base_url` 和 `model`。
6. 双击 `start_dev.bat`。
7. 浏览器访问 `http://127.0.0.1:5173`。

停止游戏可关闭两个命令窗口，或双击 `stop_dev.bat`。

## 配置示例

仓库只包含安全的 `config.example.yml`。安装脚本会在缺失时复制为 `config.yml`。

`config.yml` 包含私人API Key，已被Git忽略。不要截图、分享或提交它。

## 可选的世界书语义检索

本地语义检索分成两步：

1. 安装可选Python依赖：重新运行安装脚本并选择 `Y`，或执行：

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements-semantic.txt
   ```

2. 在游戏的世界书面板打开“语义模型管理”，下载本地模型。

模型来自Hugging Face的 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`。预计下载约486MB；CPU可以运行，建议至少预留2GB可用内存。模型、缓存和设置保存在 `data/`，不会进入Git。

若依赖、模型或网络不可用，游戏自动退回关键词检索。

## 常见问题

### 提示没有config.yml

重新启动后端会自动从安全示例建立 `config.yml`；也可以手动复制 `config.example.yml`。随后在游戏设置中填写自己的 API 配置。

### 后端窗口显示401或鉴权失败

检查API Key、Base URL和模型名是否属于同一家服务商。

### 语义模型下载中断

打开语义模型管理，点击“继续下载”。停止下载会保留断点文件；也可以卸载后重新开始。VPN、系统代理和网络服务商都会影响Hugging Face下载速度。

### 5173端口打不开

确认前端窗口没有安装错误；重新运行 `install_windows.bat`，并检查5173端口是否被其他程序占用。
