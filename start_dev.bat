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
echo [AliveWorld] The browser will open automatically when the frontend is ready.
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "$deadline=(Get-Date).AddMinutes(3); while((Get-Date)-lt $deadline){ try { $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:5173'; if($r.StatusCode -ge 200){ Start-Process 'http://127.0.0.1:5173'; break } } catch {}; Start-Sleep -Seconds 1 }"
exit /b 0
