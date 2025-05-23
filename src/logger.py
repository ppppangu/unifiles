"""
日志配置模块，使用loguru库实现日志记录
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from loguru import logger

def setup_logger():
    """
    配置日志记录器
    - 将日志保存到logs目录
    - 按天创建日志文件
    - 设置日志格式和级别
    """
    # 创建logs目录
    logs_path = Path(__file__).parent.parent / "logs"
    logs_path.mkdir(mode=0o777, exist_ok=True)
    
    # 创建OCR日志目录
    ocr_logs_path = logs_path / "ocr"
    ocr_logs_path.mkdir(mode=0o777, exist_ok=True)
    
    # 移除默认的处理器
    logger.remove()
    
    # 添加控制台处理器
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # 添加文件处理器，按天创建日志文件
    log_file = logs_path / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    logger.add(
        str(log_file),
        rotation="00:00",  # 每天午夜创建新文件
        retention="30 days",  # 保留30天的日志
        compression="zip",  # 压缩旧日志
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        level="INFO",
        encoding="utf-8",
        enqueue=True  # 异步写入，提高性能
    )
    
    # 添加错误日志文件处理器
    error_log_file = logs_path / f"error_{datetime.now().strftime('%Y-%m-%d')}.log"
    logger.add(
        str(error_log_file),
        rotation="00:00",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        level="ERROR",
        encoding="utf-8",
        enqueue=True,
        filter=lambda record: record["level"].name == "ERROR"
    )
    
    return logger

# 导出配置好的logger实例
logger = setup_logger()
