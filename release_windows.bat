@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\release_windows.ps1" %*
if errorlevel 1 (
  echo.
  echo [AliveWorld] Release workflow failed. Review the error above.
  pause
  exit /b 1
)

echo.
echo [AliveWorld] Release workflow completed.
pause
