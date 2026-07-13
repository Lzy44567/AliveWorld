@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo [AliveWorld] 可选本地语义检索依赖安装
echo.
echo 此步骤会安装 PyTorch、Transformers 等大型依赖。
echo 下载量和磁盘占用可能达到数 GB，普通游玩并不需要；不安装会自动使用关键词检索。
echo 安装完成后，语义模型本体仍需在游戏内单独下载。
echo.
if not exist ".venv\Scripts\python.exe" (
  echo 请先运行 install_windows.bat 完成基础安装。
  pause
  exit /b 1
)
choice /C YN /N /M "确认继续安装大型语义依赖？[Y/N] "
if errorlevel 2 exit /b 0
echo 正在安装，pip 会持续输出下载进度；请勿关闭窗口...
".venv\Scripts\python.exe" -m pip install -r requirements-semantic.txt
if errorlevel 1 goto :failed
echo 安装完成。现在可以在游戏内打开“语义模型管理”。
pause
exit /b 0
:failed
echo 安装失败。国内网络可配置可信的 Python 镜像后重试；PyTorch 镜像可用性因平台而异。
pause
exit /b 1
