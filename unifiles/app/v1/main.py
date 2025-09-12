"""
File Server v1 API - RESTful Architecture
符合RESTful和Python Web标准的文件服务器API

主要资源域：
1. Files - 文件存储和管理
2. Knowledge Bases - 知识库操作和文档处理

启动命令：uv run uvicorn server.app.v1.main:app --host 0.0.0.0 --port 8088 --reload
"""
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# 导入中间件和 schemas
from .middlewares import AuthMiddleware, ClientIPMiddleware, FileValidationMiddleware
from .schemas import StandardResponse

# 导入核心工具
from server.core.utils.tools import mk_need_path

# 导入API路由
from .routers import files, knowledge_bases, processors


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    try:
        # 创建必要的目录
        mk_need_path()
        logger.info("File server v1 started successfully")
    except Exception as e:
        logger.error(f"Startup initialization failed: {str(e)}")
        # Allow startup to continue

    yield

    # 关闭时执行
    logger.info("File server v1 shutting down")


def create_app() -> FastAPI:
    """创建并配置FastAPI应用实例"""

    # 日志配置
    log_path = Path(__file__).parent / "logs"
    log_path.mkdir(exist_ok=True)
    logger.add(log_path / f"{datetime.now().strftime('%Y-%m-%d')}.log", rotation="100 MB")

    app = FastAPI(
        title="File Server v1 API",
        description="A refactored, modular file server API.",
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
    app.include_router(files.router)
    app.include_router(processors.router)
    app.include_router(knowledge_bases.router)

    # 顶级健康检查路由
    @app.get("/health", response_model=StandardResponse, tags=["System"])
    async def health_check():
        """系统健康检查"""
        return StandardResponse(
            success=True,
            message="Service is healthy",
            data={"version": app.version, "service": "file-server-v1"},
        )

    return app


# 创建应用
app = create_app()

# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8088, reload=True, log_level="info")