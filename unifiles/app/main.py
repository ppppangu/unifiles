"""
Unifiles v1 API - RESTful Architecture
符合RESTful和Python Web标准的Unifiles API

主要资源域：
1. Files - 文件存储和管理
2. Knowledge Bases - 知识库操作和文档处理

启动命令：uv run uvicorn unifiles.app.main:app --host 0.0.0.0 --port 8088 --reload
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 导入核心工具
from unifiles.core.config.env_config import mk_need_path
from unifiles.core.logging import cleanup_logger, get_logger, init_logger
from unifiles.core.storage import get_initialized_storage

# 导入中间件和 schemas
from unifiles.app.middlewares import AuthMiddleware, ClientIPMiddleware, FileValidationMiddleware

# 导入API路由
from unifiles.app.routers import knowledge_bases, manager, processors, unifiles
from unifiles.app.schemas import StandardResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    try:
        # 初始化日志系统
        log_path = Path(__file__).parent / "logs"
        init_logger(
            logger_type="loguru",
            service_name="unifiles-v1",
            log_dir=log_path,
            level="INFO",
            rotation="100 MB",
            retention="30 days",
        )
        app_logger = get_logger()

        # 创建必要的目录
        mk_need_path()
        
        # 初始化存储系统
        await get_initialized_storage()
        app_logger.info("Storage system initialized")
        
        app_logger.info("Unifiles v1 started successfully", {"version": "1.1.0"})
    except Exception as e:
        app_logger = get_logger()
        app_logger.exception(
            f"Startup initialization failed: {e!s}", {"error_type": "startup_error"}
        )
        # Allow startup to continue

    yield

    # 关闭时执行
    app_logger = get_logger()
    app_logger.info("Unifiles v1 shutting down")
    cleanup_logger()


def create_app() -> FastAPI:
    """创建并配置FastAPI应用实例"""

    app = FastAPI(
        title="Unifiles v1 API",
        description="A refactored, modular unifiles API.",
        version="1.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # 添加自定义中间件
    app.add_middleware(ClientIPMiddleware)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(FileValidationMiddleware)

    # 包含API路由
    app.include_router(unifiles.router)
    app.include_router(processors.router)
    app.include_router(knowledge_bases.router)
    app.include_router(manager.router)

    # 顶级健康检查路由
    @app.get("/health", response_model=StandardResponse, tags=["System"])
    async def health_check():
        """系统健康检查"""
        return StandardResponse(
            success=True,
            message="Service is healthy",
            data={"version": app.version, "service": "unifiles-v1"},
        )

    return app


# 创建应用
app = create_app()

# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8088, reload=True, log_level="info")
