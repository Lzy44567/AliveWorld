"""AliveWorld FastAPI application for source development and packaged builds."""

from __future__ import annotations

import datetime
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.v1.asset_workshop_routes import router as asset_workshop_router
from api.v1.causal_ledger_routes import router as causal_ledger_router
from api.v1.game_routes import router as game_router
from api.v1.feedback_routes import router as feedback_router
from api.v1.image_generation_routes import router as image_generation_router
from api.v1.lobby_routes import router as lobby_router
from api.v1.local_asset_routes import router as local_asset_router
from api.v1.model_connection_routes import router as model_connection_router
from api.v1.preference_workshop_routes import router as preference_workshop_router
from api.v1.story_memory_routes import router as story_memory_router
from api.v1.user_preference_routes import router as user_preference_router
from api.v1.update_routes import router as update_router
from api.v1.worldbook_workshop_routes import router as worldbook_workshop_router
from api.v1.world_package_routes import router as world_package_router
from utils.runtime_paths import PATHS
from utils.sys_logger import init_logger
from utils.version import APP_VERSION


def _configured_cors_origins() -> list[str]:
    raw = os.environ.get("ALIVEWORLD_CORS_ORIGINS", "")
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


def create_app(
    *,
    frontend_dist: str | Path | None = None,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    application = FastAPI(title="AliveWorld Engine", version=APP_VERSION)
    allowed_origins = _configured_cors_origins() if cors_origins is None else cors_origins
    if allowed_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Content-Type"],
        )

    application.include_router(game_router, prefix="/api/v1/game", tags=["Game 推演核心"])
    application.include_router(local_asset_router, prefix="/api/v1/game", tags=["Game 局内专属资产"])
    application.include_router(causal_ledger_router, prefix="/api/v1/game", tags=["Game 暗流因果账本"])
    application.include_router(lobby_router, prefix="/api/v1/lobby", tags=["大厅与资产"])
    application.include_router(worldbook_workshop_router, prefix="/api/v1/worldbooks", tags=["世界书工坊"])
    application.include_router(world_package_router, prefix="/api/v1/world-packages", tags=["世界包与一键开始"])
    application.include_router(image_generation_router, prefix="/api/v1/game", tags=["Game 异步生图"])
    application.include_router(story_memory_router, prefix="/api/v1/game", tags=["Game 分级故事记忆"])
    application.include_router(user_preference_router, prefix="/api/v1/preferences", tags=["用户偏好卡"])
    application.include_router(
        preference_workshop_router,
        prefix="/api/v1/preferences/workshops",
        tags=["用户偏好工坊"],
    )
    application.include_router(
        asset_workshop_router,
        prefix="/api/v1/asset-workshops",
        tags=["角色文风实体工坊"],
    )
    application.include_router(update_router, prefix="/api/v1/updates", tags=["版本更新"])
    application.include_router(feedback_router, prefix="/api/v1/feedback", tags=["反馈与诊断"])
    application.include_router(
        model_connection_router,
        prefix="/api/v1/model-connections",
        tags=["接口配置与功能用途"],
    )

    @application.get("/api/health", tags=["运行状态"])
    def health(response: Response):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return {
            "status": "ok",
            "version": APP_VERSION,
            "packaged": PATHS.frozen,
        }

    static_root = Path(frontend_dist or PATHS.frontend_dist).resolve()
    index_file = static_root / "index.html"
    assets_dir = static_root / "assets"
    if index_file.is_file():
        if assets_dir.is_dir():
            application.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

        @application.get("/{requested_path:path}", include_in_schema=False)
        def frontend(requested_path: str):
            if requested_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="API route not found")
            candidate = (static_root / requested_path).resolve()
            if candidate.is_relative_to(static_root) and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(index_file, headers={"Cache-Control": "no-store, max-age=0"})
    else:
        @application.get("/", include_in_schema=False)
        def source_root():
            return {
                "message": "AliveWorld Engine is running.",
                "version": APP_VERSION,
                "frontend": "Run the Vite development server or build aliveworld-ui/dist.",
            }

    return application


init_logger(str(PATHS.log_dir / f"run_{datetime.datetime.now():%Y%m%d}.log"))
app = create_app()
