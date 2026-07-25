@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [AliveWorld] Build environment is missing. Run install_windows.bat first.
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\build_windows_portable.ps1"
if errorlevel 1 (
  echo.
  echo [AliveWorld] Build failed. Review the error above.
  pause
  exit /b 1
)

echo.
echo [AliveWorld] Portable package created in the release directory.
pause
