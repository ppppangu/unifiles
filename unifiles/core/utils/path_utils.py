"""
路径工具函数

提供项目中常用的路径创建和管理功能。
"""

from pathlib import Path
from loguru import logger


def get_project_root() -> Path:
    """
    获取项目根目录

    Returns:
        项目根目录路径
    """
    # 从当前文件向上找到项目根目录
    current = Path(__file__).parent.parent.parent
    return current


def mk_logs_path() -> Path:
    """
    创建日志目录

    Returns:
        日志目录路径
    """
    log_path = get_project_root() / "logs"
    log_path.mkdir(mode=0o777, exist_ok=True)
    logger.debug(f"Logs directory ensured: {log_path}")
    return log_path


def mk_temp_path() -> Path:
    """
    创建临时目录

    Returns:
        临时目录路径
    """
    temp_path = get_project_root() / "tmp"
    temp_path.mkdir(mode=0o777, exist_ok=True)
    logger.debug(f"Temp directory ensured: {temp_path}")
    return temp_path


def mk_need_path() -> None:
    """创建必要的目录"""
    mk_logs_path()
    mk_temp_path()
    logger.info("Required directories created")
