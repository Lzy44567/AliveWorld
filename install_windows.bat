@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo [AliveWorld] 基础环境安装（不包含大型本地语义模型依赖）
echo 需要提前安装 Python 3.12 和 Node.js 20+。首次安装时间取决于网络速度。

where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON=py -3.12"
) else (
  where python >nul 2>nul || goto :missing_python
  set "PYTHON=python"
)

where node >nul 2>nul || goto :missing_node
where npm >nul 2>nul || goto :missing_node

if not exist ".venv\Scripts\python.exe" (
  echo Creating project-local Python environment...
  %PYTHON% -m venv .venv || goto :failed
)

echo [1/3] 正在安装后端基础依赖...
".venv\Scripts\python.exe" -m pip install --upgrade pip || goto :failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :failed

echo [2/3] 正在安装前端依赖...
pushd aliveworld-ui
call npm install || (popd & goto :failed)
popd

echo [3/3] 正在准备本地配置文件...
if not exist config.yml copy config.example.yml config.yml >nul

:done
echo.
echo 基础安装完成。此过程不会安装 PyTorch。
echo 1. 编辑 config.yml，填写 API Key、Base URL 和模型名。
echo 2. 双击 start_dev.bat 启动。
echo 3. 只有需要本地语义检索时，才运行 install_semantic_windows.bat。
pause
exit /b 0

:missing_python
echo 未找到 Python 3.12，请先从 https://www.python.org/downloads/ 安装。
pause
exit /b 1

:missing_node
echo 未找到 Node.js 20+，请先从 https://nodejs.org/ 安装 LTS 版本。
pause
exit /b 1

:failed
echo Installation failed. Review the error above and docs/INSTALL_WINDOWS.md.
pause
exit /b 1
