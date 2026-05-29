# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.v1.game_routes import router as game_router
from utils.sys_logger import init_logger
import os, datetime
from api.v1.lobby_routes import router as lobby_router

# 初始化日志体系 (复用 V1.0 的优秀资产)
os.makedirs("logs", exist_ok=True)
init_logger(f"logs/run_v2_{datetime.datetime.now().strftime('%Y%m%d')}.log")

app = FastAPI(
    title="AliveWorld V2 Engine",
    description="商业化沙盘推演后端接口",
    version="2.0.0"
)

# 允许跨域请求 (CORS)，为 Vue/Tauri 前端铺路
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 开发阶段允许所有前端访问
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
app.include_router(game_router, prefix="/api/v1/game", tags=["Game 推演核心"])
app.include_router(lobby_router, prefix="/api/v1/lobby", tags=["大厅与资产"])

@app.get("/")
def read_root():
    return {"message": "AliveWorld V2 Engine is running. Visit /docs for Swagger UI."}