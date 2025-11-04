"""
统一日志管理模块

新版（推荐）:
- UnifiedLogger: 统一日志记录器（简化版）
- get_logger: 工厂函数
- with_context: 上下文管理器
- LogBackgroundFlusher: 后台刷新器

使用示例（新版）:
    from unifiles.core.logging import get_logger, with_context

    logger = get_logger(__name__, service_layer='app')

    with with_context(user_id="user_123"):
        await logger.info("User action", extra={"action": "upload"})

旧版（兼容）:
- LoguruLogger: 基于 Loguru 的文件日志
- PostgreSQLLogger: 基于 PostgreSQL 的数据库日志
- HybridLogger: 混合日志实现
"""

# 新版日志系统（推荐使用）
from .unified import (
    UnifiedLogger,
    get_logger,
    with_context,
)

from .background_flusher import (
    LogBackgroundFlusher,
    get_log_flusher,
    start_log_flusher,
    stop_log_flusher,
)

# 旧版日志系统（向后兼容，逐步淘汰）
try:
    from .logging import (
        BaseLogger,
        HybridLogger,
        LoguruLogger,
        PostgreSQLLogger,
        cleanup_logger,
        init_logger,
    )
    _has_legacy_logging = True
except ImportError:
    _has_legacy_logging = False

__all__ = [
    # 新版（推荐）
    "UnifiedLogger",
    "get_logger",
    "with_context",
    "LogBackgroundFlusher",
    "get_log_flusher",
    "start_log_flusher",
    "stop_log_flusher",
]

# 添加旧版导出（如果存在）
if _has_legacy_logging:
    __all__.extend([
        "BaseLogger",
        "HybridLogger",
        "LoguruLogger",
        "PostgreSQLLogger",
        "cleanup_logger",
        "init_logger",
    ])
