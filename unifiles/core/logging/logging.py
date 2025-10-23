import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

from loguru import logger


class BaseLogger(ABC):
    """日志系统基类，定义统一的日志接口"""

    def __init__(self, service_name: str = "unifiles"):
        self.service_name = service_name
        self._setup()

    @abstractmethod
    def _setup(self) -> None:
        """初始化日志系统配置"""
        pass

    @abstractmethod
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录信息级别日志"""
        pass

    @abstractmethod
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录警告级别日志"""
        pass

    @abstractmethod
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录错误级别日志"""
        pass

    @abstractmethod
    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录调试级别日志"""
        pass

    @abstractmethod
    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录严重错误级别日志"""
        pass


class LoguruLogger(BaseLogger):
    """基于 Loguru 的文件日志实现"""

    def __init__(
        self,
        service_name: str = "unifiles",
        log_dir: Optional[Union[str, Path]] = None,
        rotation: str = "100 MB",
        retention: str = "30 days",
        compression: str = "zip",
        level: str = "INFO",
    ):
        # Default to project-level logs directory when not provided
        default_logs = Path(__file__).resolve().parents[3] / "logs"
        self.log_dir = Path(log_dir) if log_dir else default_logs
        self.rotation = rotation
        self.retention = retention
        self.compression = compression
        self.level = level
        self._console_handler_id = None  # 控制台handler ID
        self._file_handler_id = None     # 文件handler ID
        super().__init__(service_name)

    def _setup(self) -> None:
        """配置 Loguru 日志系统"""
        # 创建日志目录
        self.log_dir.mkdir(exist_ok=True)

        # 移除默认的控制台处理器
        logger.remove()

        # 添加控制台输出（开发时有用）- 保存handler ID
        self._console_handler_id = logger.add(
            sink=lambda msg: print(msg, end=""),
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>",
            level=self.level,
            # Temporarily removed filter for debugging
            # filter=lambda record: record["extra"].get("service") == self.service_name,
        )

        # 添加文件输出
        log_file = (
            self.log_dir
            / f"{self.service_name}_{datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')}.log"
        )
        self._file_handler_id = logger.add(
            sink=str(log_file),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            level=self.level,
            rotation=self.rotation,
            retention=self.retention,
            compression=self.compression,
            encoding="utf-8",
            # Temporarily removed filter for debugging
            # filter=lambda record: record["extra"].get("service") == self.service_name,
        )

    def _log_with_context(
        self, level: str, message: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """带上下文信息的日志记录，定位到业务调用处"""
        context = {"service": self.service_name}
        if extra:
            context.update(extra)

        # Use opt(depth=2) so the reported source is the original caller
        logger.bind(**context).opt(depth=2).log(level.upper(), message)

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录信息级别日志"""
        self._log_with_context("INFO", message, extra)

    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录警告级别日志"""
        self._log_with_context("WARNING", message, extra)

    def error(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录错误级别日志"""
        self._log_with_context("ERROR", message, extra)

    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录调试级别日志"""
        self._log_with_context("DEBUG", message, extra)

    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录严重错误级别日志"""
        self._log_with_context("CRITICAL", message, extra)

    def exception(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录异常信息（包含堆栈跟踪），定位到业务调用处"""
        context = {"service": self.service_name}
        if extra:
            context.update(extra)
        logger.bind(**context).opt(depth=2).exception(message)

    def cleanup(self) -> None:
        """清理日志系统资源"""
        # 移除控制台handler
        if self._console_handler_id is not None:
            try:
                logger.remove(self._console_handler_id)
            except ValueError:
                # Handler可能已经被移除
                pass
            self._console_handler_id = None

        # 移除文件handler
        if self._file_handler_id is not None:
            try:
                logger.remove(self._file_handler_id)
            except ValueError:
                # Handler可能已经被移除
                pass
            self._file_handler_id = None


class PostgreSQLLogger(BaseLogger):
    """基于 PostgreSQL 的数据库日志实现（占位，后续实现）"""

    def _setup(self) -> None:
        """初始化 PostgreSQL 连接"""
        # TODO: 实现 PostgreSQL 日志存储
        pass

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        # TODO: 实现数据库日志记录
        pass

    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        # TODO: 实现数据库日志记录
        pass

    def error(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        # TODO: 实现数据库日志记录
        pass

    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        # TODO: 实现数据库日志记录
        pass

    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        # TODO: 实现数据库日志记录
        pass


class HybridLogger(BaseLogger):
    """混合日志实现，同时支持文件和数据库存储"""

    def __init__(
        self,
        service_name: str = "unifiles",
        file_logger_config: Optional[Dict[str, Any]] = None,
        db_logger_config: Optional[Dict[str, Any]] = None,
    ):
        self.file_logger_config = file_logger_config or {}
        self.db_logger_config = db_logger_config or {}
        self.file_logger: Optional[LoguruLogger] = None
        self.db_logger: Optional[PostgreSQLLogger] = None
        super().__init__(service_name)

    def _setup(self) -> None:
        """初始化混合日志系统"""
        # 初始化文件日志
        self.file_logger = LoguruLogger(
            service_name=self.service_name, **self.file_logger_config
        )

        # TODO: 后续启用数据库日志时取消注释
        # self.db_logger = PostgreSQLLogger(
        #     service_name=self.service_name,
        #     **self.db_logger_config
        # )

    def _log_to_all(
        self, level: str, message: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """向所有日志后端记录日志"""
        if self.file_logger:
            getattr(self.file_logger, level.lower())(message, extra)

        # TODO: 后续启用数据库日志时取消注释
        # if self.db_logger:
        #     getattr(self.db_logger, level.lower())(message, extra)

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._log_to_all("INFO", message, extra)

    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._log_to_all("WARNING", message, extra)

    def error(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._log_to_all("ERROR", message, extra)

    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._log_to_all("DEBUG", message, extra)

    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._log_to_all("CRITICAL", message, extra)

    def exception(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录异常信息"""
        if self.file_logger:
            self.file_logger.exception(message, extra)

    def cleanup(self) -> None:
        """清理所有日志系统资源"""
        if self.file_logger:
            self.file_logger.cleanup()
        # TODO: 清理数据库连接


# 全局日志实例
app_logger: Optional[BaseLogger] = None


def _read_logging_env() -> Dict[str, Any]:
    """Read logging configuration from environment variables with sensible defaults."""
    # Service name
    service_name = os.getenv("UNIFILES_SERVICE_NAME", "unifiles-v1")

    # Directory for log files
    log_dir_env = os.getenv("UNIFILES_API_LOG_DIR")
    log_dir = (
        Path(log_dir_env)
        if log_dir_env
        else Path(__file__).resolve().parents[3] / "logs"
    )

    # Other settings
    level = os.getenv("UNIFILES_API_LOG_LEVEL", "INFO").upper()
    rotation = os.getenv("UNIFILES_API_LOG_ROTATION", "100 MB")
    retention = os.getenv("UNIFILES_API_LOG_RETENTION", "30 days")
    compression = os.getenv("UNIFILES_API_LOG_COMPRESSION", "zip")

    return {
        "service_name": service_name,
        "log_dir": log_dir,
        "level": level,
        "rotation": rotation,
        "retention": retention,
        "compression": compression,
    }


def get_logger() -> BaseLogger:
    """获取全局日志实例"""
    global app_logger
    if app_logger is None:
        # 默认使用 Loguru 文件日志（读取环境变量配置）
        cfg = _read_logging_env()
        app_logger = LoguruLogger(**cfg)
    return app_logger


def init_logger(
    logger_type: str = "loguru", service_name: str = "unifiles", **kwargs
) -> BaseLogger:
    """初始化全局日志系统

    Args:
        logger_type: 日志类型 ("loguru", "postgresql", "hybrid")
        service_name: 服务名称
        **kwargs: 传递给具体日志实现的配置参数

    Returns:
        初始化后的日志实例
    """
    global app_logger

    if logger_type == "loguru":
        # If no explicit kwargs provided, load from environment
        if not kwargs and service_name == "unifiles":
            cfg = _read_logging_env()
            app_logger = LoguruLogger(**cfg)
        else:
            app_logger = LoguruLogger(service_name=service_name, **kwargs)
    elif logger_type == "postgresql":
        app_logger = PostgreSQLLogger(service_name=service_name, **kwargs)
    elif logger_type == "hybrid":
        app_logger = HybridLogger(service_name=service_name, **kwargs)
    else:
        raise ValueError(f"Unsupported logger type: {logger_type}")

    return app_logger


def cleanup_logger() -> None:
    """清理全局日志系统"""
    global app_logger
    if app_logger and hasattr(app_logger, "cleanup"):
        app_logger.cleanup()
    app_logger = None
