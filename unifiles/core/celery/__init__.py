"""
Celery 异步任务队列模块
用于处理耗时的 OCR 提取任务
"""

from unifiles.core.celery.app import celery_app

__all__ = ["celery_app"]
