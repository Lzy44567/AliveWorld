@echo off
echo [AliveWorld V2] 正在启动双核引擎...

:: 启动后端 FastAPI (独立窗口)
start "AW_Backend" cmd /k "python -m uvicorn main:app --reload --port 8000"

:: 启动前端 Vite (独立窗口)
start "AW_Frontend" cmd /k "cd aliveworld-ui && npm run dev"

echo 启动指令已发送！请等待几秒后访问 http://localhost:5173