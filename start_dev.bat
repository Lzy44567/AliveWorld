@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [AliveWorld] Project environment is missing. Run install_windows.bat first.
  pause
  exit /b 1
)
if not exist "config.yml" (
  echo [AliveWorld] config.yml is missing. Copy config.example.yml and fill in your API settings.
  pause
  exit /b 1
)
if not exist "aliveworld-ui\node_modules" (
  echo [AliveWorld] Frontend dependencies are missing. Run install_windows.bat first.
  pause
  exit /b 1
)

echo [AliveWorld] Starting backend and frontend...
start "AW_Backend" cmd /k "cd /d ""%~dp0"" && .venv\Scripts\python.exe -m uvicorn main:app --port 8000"
start "AW_Frontend" cmd /k "cd /d ""%~dp0aliveworld-ui"" && npm run dev"
echo Open http://127.0.0.1:5173 after both windows are ready.
pause
