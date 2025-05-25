"""
内存监控工具
"""
import psutil
import gc
from typing import Dict, Any
from src.logger import logger


def get_memory_info() -> Dict[str, Any]:
    """获取当前内存使用情况"""
    process = psutil.Process()
    memory_info = process.memory_info()
    
    return {
        "rss_mb": memory_info.rss / 1024 / 1024,  # 物理内存使用
        "vms_mb": memory_info.vms / 1024 / 1024,  # 虚拟内存使用
        "percent": process.memory_percent(),       # 内存使用百分比
        "available_mb": psutil.virtual_memory().available / 1024 / 1024,
        "total_mb": psutil.virtual_memory().total / 1024 / 1024,
    }


def log_memory_usage(context: str = ""):
    """记录内存使用情况"""
    info = get_memory_info()
    logger.info(
        f"内存使用 {context}: "
        f"RSS={info['rss_mb']:.1f}MB, "
        f"VMS={info['vms_mb']:.1f}MB, "
        f"使用率={info['percent']:.1f}%, "
        f"可用={info['available_mb']:.1f}MB"
    )


def force_gc():
    """强制垃圾回收"""
    collected = gc.collect()
    logger.debug(f"垃圾回收完成，回收了 {collected} 个对象")
    return collected


class MemoryMonitor:
    """内存监控上下文管理器"""
    
    def __init__(self, context: str):
        self.context = context
        self.start_memory = None
    
    def __enter__(self):
        self.start_memory = get_memory_info()
        log_memory_usage(f"开始 {self.context}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_memory = get_memory_info()
        memory_diff = end_memory["rss_mb"] - self.start_memory["rss_mb"]
        
        logger.info(
            f"完成 {self.context}: "
            f"内存变化={memory_diff:+.1f}MB, "
            f"当前使用={end_memory['rss_mb']:.1f}MB"
        )
        
        # 如果内存增长超过50MB，强制垃圾回收
        if memory_diff > 50:
            logger.warning(f"{self.context} 内存增长过多，执行垃圾回收")
            force_gc()
