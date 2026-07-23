# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.v1.game_routes import router as game_router
from api.v1.local_asset_routes import router as local_asset_router # 引入新路由
from api.v1.lobby_routes import router as lobby_router
from api.v1.causal_ledger_routes import router as causal_ledger_router
from api.v1.worldbook_workshop_routes import router as worldbook_workshop_router
from api.v1.image_generation_routes import router as image_generation_router
from api.v1.story_memory_routes import router as story_memory_router
from api.v1.user_preference_routes import router as user_preference_router
from api.v1.preference_workshop_routes import router as preference_workshop_router
from utils.sys_logger import init_logger
import os, datetime

os.makedirs("logs", exist_ok=True)
init_logger(f"logs/run_v2_{datetime.datetime.now().strftime('%Y%m%d')}.log")

app = FastAPI(title="AliveWorld Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(game_router, prefix="/api/v1/game", tags=["Game 推演核心"])
# 挂载局内资产路由 (前缀一致，只是代码分家了)
app.include_router(local_asset_router, prefix="/api/v1/game", tags=["Game 局内专属资产"])
app.include_router(causal_ledger_router, prefix="/api/v1/game", tags=["Game 暗流因果账本"])
app.include_router(lobby_router, prefix="/api/v1/lobby", tags=["大厅与资产"])
app.include_router(worldbook_workshop_router, prefix="/api/v1/worldbooks", tags=["世界书工坊"])
app.include_router(image_generation_router, prefix="/api/v1/game", tags=["Game 异步生图"])
app.include_router(story_memory_router, prefix="/api/v1/game", tags=["Game 分级故事记忆"])
app.include_router(user_preference_router, prefix="/api/v1/preferences", tags=["用户偏好卡"])
app.include_router(preference_workshop_router, prefix="/api/v1/preferences/workshops", tags=["用户偏好工坊"])

@app.get("/")
def read_root(): return {"message": "AliveWorld V2 Engine is running."}
