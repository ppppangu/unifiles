"""
统一日志管理模块

提供多种日志后端实现：
- LoguruLogger: 基于 Loguru 的文件日志
- PostgreSQLLogger: 基于 PostgreSQL 的数据库日志  
- HybridLogger: 混合日志实现

使用示例:
    from unifiles.core.logging import get_logger, init_logger
    
    # 初始化日志系统
    init_logger(logger_type="loguru", service_name="unifiles-v1")
    
    # 获取日志实例
    logger = get_logger()
    logger.info("Application started")
"""

from .logging import (
    BaseLogger,
    HybridLogger,
    LoguruLogger,
    PostgreSQLLogger,
    cleanup_logger,
    get_logger,
    init_logger,
)

__all__ = [
    "BaseLogger",
    "LoguruLogger", 
    "PostgreSQLLogger",
    "HybridLogger",
    "get_logger",
    "init_logger", 
    "cleanup_logger",
]