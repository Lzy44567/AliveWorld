@echo off
setlocal
cd /d "%~dp0"
echo [AliveWorld] Windows installation

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

echo Installing backend dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip || goto :failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :failed

echo Installing frontend dependencies...
pushd aliveworld-ui
call npm install || (popd & goto :failed)
popd

if not exist config.yml copy config.example.yml config.yml >nul

echo.
choice /C YN /N /M "Install optional local semantic retrieval dependencies? This may download a large PyTorch package. [Y/N] "
if errorlevel 2 goto :done
echo Installing optional semantic dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements-semantic.txt || goto :failed

:done
echo.
echo Installation complete.
echo 1. Edit config.yml and fill in your own API key, base URL and model.
echo 2. Double-click start_dev.bat.
pause
exit /b 0

:missing_python
echo Python 3.12 was not found. Install it from https://www.python.org/downloads/
pause
exit /b 1

:missing_node
echo Node.js 20 or newer was not found. Install the LTS version from https://nodejs.org/
pause
exit /b 1

:failed
echo Installation failed. Review the error above and docs/INSTALL_WINDOWS.md.
pause
exit /b 1
