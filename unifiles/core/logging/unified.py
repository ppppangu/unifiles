"""
统一日志系统 - 核心实现 (简化版)

特性：
1. 自动注入 trace_id/span_id (关联OTEL Traces)
2. 智能路由（本地/队列）
3. Redis 队列异步写入
4. 配置驱动
5. ERROR/CRITICAL添加Span Events

简化说明:
- 移除OTEL Logs集成（过度设计）
- 保留trace_id/span_id注入（关联OTEL Traces）
- 保留Span Events（ERROR/CRITICAL级别）
"""

import asyncio
import json
import os
import random
import socket
import threading
import time
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger as loguru_logger
from opentelemetry import trace

from unifiles.config.settings import settings, get_runtime_config
from unifiles.core.queue.redis_queue import get_queue_service

# 上下文变量（线程安全）
_ctx_user_id: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
_ctx_file_id: ContextVar[Optional[str]] = ContextVar('file_id', default=None)
_ctx_task_id: ContextVar[Optional[str]] = ContextVar('task_id', default=None)


class UnifiedLogger:
    """统一日志记录器（简化版）"""

    # 队列名称
    LOG_QUEUE_NAME = "unifiles:queue:logs"

    def __init__(self, name: str, service_layer: str):
        """
        初始化日志记录器

        Args:
            name: 模块名（通常使用 __name__）
            service_layer: 服务层次 ('app' | 'worker' | 'core')
        """
        self.name = name
        self.service_layer = service_layer

        # 获取队列服务
        self.queue_service = get_queue_service()

        # 配置缓存（5秒过期）
        self._config_cache: Dict[str, Any] = {}
        self._config_cache_time: Dict[str, float] = {}

    def _enrich_context(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        """自动注入 trace_id、span_id、环境信息"""

        enriched = extra.copy()

        # 1. OTEL trace 信息（关联OTEL Traces）
        span = trace.get_current_span()
        ctx = span.get_span_context()

        if ctx.is_valid:
            enriched['trace_id'] = format(ctx.trace_id, '032x')
            enriched['span_id'] = format(ctx.span_id, '016x')

        # 2. 服务信息
        enriched['service_layer'] = self.service_layer
        enriched['service_name'] = self.name

        # 3. 环境信息
        enriched['hostname'] = socket.gethostname()
        enriched['process_id'] = os.getpid()
        enriched['thread_name'] = threading.current_thread().name

        # 4. 上下文变量
        if user_id := _ctx_user_id.get():
            enriched.setdefault('user_id', user_id)
        if file_id := _ctx_file_id.get():
            enriched.setdefault('file_id', file_id)
        if task_id := _ctx_task_id.get():
            enriched.setdefault('task_id', task_id)

        # 5. 代码位置（通过 loguru 的 frame）
        import inspect
        frame = inspect.currentframe()
        if frame and frame.f_back and frame.f_back.f_back:
            caller_frame = frame.f_back.f_back
            enriched['module_name'] = caller_frame.f_globals.get('__name__')
            enriched['function_name'] = caller_frame.f_code.co_name
            enriched['line_number'] = caller_frame.f_lineno

        return enriched

    async def _should_enqueue(self, level: str, enriched: Dict) -> bool:
        """路由决策：是否入队写入数据库"""

        # 1. 全局开关
        db_enabled = await self._get_config_cached('logging.db_enabled', default=True)
        if not db_enabled:
            return False

        # 2. 级别优先级
        level_priority = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3, 'CRITICAL': 4}
        current_priority = level_priority[level]

        # 3. 按层次判断
        if self.service_layer == 'core':
            # Core层：WARNING及以上必入队
            if current_priority >= 2:
                return True
            # INFO级别：标记为重要的入队
            if level == 'INFO' and enriched.get('important', False):
                return True
            # 其他INFO：采样（默认10%）
            if level == 'INFO':
                sample_rate = await self._get_config_cached('logging.core_info_sample_rate', default=0.1)
                return random.random() < sample_rate
            return False

        elif self.service_layer == 'worker':
            # Worker层：任务相关日志
            if 'task_id' in enriched:
                # 进度日志：采样（10%, 20%, ..., 100%）
                if 'progress' in enriched:
                    progress = enriched['progress']
                    return progress % 10 == 0
                # 其他任务日志：INFO及以上
                return current_priority >= 1
            return current_priority >= 2

        elif self.service_layer == 'app':
            # App层：用户操作、认证、ERROR及以上
            if 'user_id' in enriched or 'auth' in enriched.get('operation', ''):
                return current_priority >= 1
            return current_priority >= 2

        return False

    async def _get_config_cached(self, key: str, default: Any) -> Any:
        """带缓存的配置获取（减少Redis查询）"""
        now = time.time()

        if key in self._config_cache:
            if now - self._config_cache_time.get(key, 0) < 5:  # 5秒缓存
                return self._config_cache[key]

        value = await get_runtime_config(key, default)
        self._config_cache[key] = value
        self._config_cache_time[key] = now
        return value

    async def _enqueue_log(self, level: str, message: str, enriched: Dict):
        """将日志入队（Redis队列）"""

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message,
            **enriched
        }

        try:
            # 入队到 Redis
            await self.queue_service.enqueue(
                queue_name=self.LOG_QUEUE_NAME,
                task=log_entry,
                priority=0  # 日志队列不使用优先级
            )
        except Exception as e:
            # 队列失败不应影响业务，仅本地记录
            loguru_logger.error(f"Failed to enqueue log: {e}")

    async def _log(self, level: str, message: str, extra: Dict):
        """核心日志方法（二路输出）"""

        # 1. 丰富上下文
        enriched = self._enrich_context(extra)

        # 2. 写入本地文件（loguru，所有级别）
        loguru_logger.bind(**enriched).log(level, message)

        # 3. 路由决策：是否入队
        if await self._should_enqueue(level, enriched):
            await self._enqueue_log(level, message, enriched)

        # 4. 添加 OTEL Span Event（ERROR/CRITICAL）
        if level in ('ERROR', 'CRITICAL'):
            span = trace.get_current_span()
            if span.is_recording():
                span.add_event(
                    f"log.{level.lower()}",
                    attributes={
                        'log.message': message,
                        'log.level': level,
                        **{k: str(v) for k, v in enriched.items() if k not in ('stack_trace',)}
                    }
                )

    # ===== 同步方法 (推荐使用，像loguru一样简单) =====

    def info(self, message: str, **kwargs):
        """记录INFO级别日志（同步调用）"""
        extra = kwargs.get('extra', {})
        self._log_sync('INFO', message, extra)

    def warning(self, message: str, **kwargs):
        """记录WARNING级别日志（同步调用）"""
        extra = kwargs.get('extra', {})
        self._log_sync('WARNING', message, extra)

    def error(self, message: str, **kwargs):
        """记录ERROR级别日志（同步调用，自动捕获异常堆栈）"""
        extra = kwargs.get('extra', {})

        # 自动捕获异常信息
        if exc_info := kwargs.get('exc_info'):
            import traceback
            extra['exception_type'] = type(exc_info).__name__
            extra['exception_message'] = str(exc_info)
            extra['stack_trace'] = ''.join(
                traceback.format_exception(
                    type(exc_info),
                    exc_info,
                    exc_info.__traceback__
                )
            )

        self._log_sync('ERROR', message, extra)

    def critical(self, message: str, **kwargs):
        """记录CRITICAL级别日志（同步调用）"""
        extra = kwargs.get('extra', {})
        self._log_sync('CRITICAL', message, extra)

    def debug(self, message: str, **kwargs):
        """记录DEBUG级别日志（同步调用，仅本地，不入队）"""
        extra = kwargs.get('extra', {})
        enriched = self._enrich_context(extra)

        # DEBUG级别仅写本地文件
        loguru_logger.bind(**enriched).debug(message)

    # ===== 异步方法 (高级用法) =====

    async def ainfo(self, message: str, **kwargs):
        """记录INFO级别日志（异步调用）"""
        await self._log('INFO', message, kwargs.get('extra', {}))

    async def awarning(self, message: str, **kwargs):
        """记录WARNING级别日志（异步调用）"""
        await self._log('WARNING', message, kwargs.get('extra', {}))

    async def aerror(self, message: str, **kwargs):
        """记录ERROR级别日志（异步调用，自动捕获异常堆栈）"""
        extra = kwargs.get('extra', {})

        # 自动捕获异常信息
        if exc_info := kwargs.get('exc_info'):
            import traceback
            extra['exception_type'] = type(exc_info).__name__
            extra['exception_message'] = str(exc_info)
            extra['stack_trace'] = ''.join(
                traceback.format_exception(
                    type(exc_info),
                    exc_info,
                    exc_info.__traceback__
                )
            )

        await self._log('ERROR', message, extra)

    async def acritical(self, message: str, **kwargs):
        """记录CRITICAL级别日志（异步调用）"""
        await self._log('CRITICAL', message, kwargs.get('extra', {}))

    async def adebug(self, message: str, **kwargs):
        """记录DEBUG级别日志（异步调用，仅本地，不入队）"""
        extra = kwargs.get('extra', {})
        enriched = self._enrich_context(extra)

        # DEBUG级别仅写本地文件
        loguru_logger.bind(**enriched).debug(message)

    def _log_sync(self, level: str, message: str, extra: Dict):
        """同步日志方法（后台异步处理）"""

        # 1. 丰富上下文
        enriched = self._enrich_context(extra)

        # 2. 立即写入本地文件（同步）
        loguru_logger.bind(**enriched).log(level, message)

        # 3. 后台异步处理队列写入和Span Events
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在运行中的事件循环中创建任务
                asyncio.create_task(self._async_processing(level, message, enriched))
            else:
                # 没有事件循环，直接同步处理（仅本地日志）
                pass
        except RuntimeError:
            # 没有事件循环，仅本地日志
            pass

    async def _async_processing(self, level: str, message: str, enriched: Dict):
        """后台异步处理（队列写入 + Span Events）"""

        # 1. 路由决策：是否入队
        if await self._should_enqueue(level, enriched):
            await self._enqueue_log(level, message, enriched)

        # 2. 添加 OTEL Span Event（ERROR/CRITICAL）
        if level in ('ERROR', 'CRITICAL'):
            span = trace.get_current_span()
            if span.is_recording():
                span.add_event(
                    f"log.{level.lower()}",
                    attributes={
                        'log.message': message,
                        'log.level': level,
                        **{k: str(v) for k, v in enriched.items() if k not in ('stack_trace',)}
                    }
                )


# ===== 工厂方法 =====

def get_logger(name: str, service_layer: str = 'core') -> UnifiedLogger:
    """
    获取统一日志记录器

    Args:
        name: 模块名（通常使用 __name__）
        service_layer: 服务层次 ('app' | 'worker' | 'core')

    Returns:
        UnifiedLogger 实例

    使用示例（推荐 - 同步调用）:
        logger = get_logger(__name__, service_layer='app')
        logger.info("User logged in", extra={"user_id": "123"})
        logger.error("Processing failed", exc_info=e, extra={"file_id": "456"})

    高级用法（异步调用）:
        logger = get_logger(__name__, service_layer='worker')
        await logger.ainfo("Task started", extra={"task_id": "123"})
    """
    return UnifiedLogger(name, service_layer)


# ===== 上下文管理器 =====

class LogContext:
    """日志上下文管理器（自动注入user_id等）"""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.tokens = {}

    def __enter__(self):
        if 'user_id' in self.kwargs:
            self.tokens['user_id'] = _ctx_user_id.set(self.kwargs['user_id'])
        if 'file_id' in self.kwargs:
            self.tokens['file_id'] = _ctx_file_id.set(self.kwargs['file_id'])
        if 'task_id' in self.kwargs:
            self.tokens['task_id'] = _ctx_task_id.set(self.kwargs['task_id'])
        return self

    def __exit__(self, *args):
        for token in self.tokens.values():
            token.var.reset(token)


def with_context(**kwargs):
    """
    日志上下文（自动注入到所有日志）

    使用示例:
        with with_context(user_id="user_123", file_id="file_456"):
            await logger.info("Processing file")  # 自动包含 user_id 和 file_id
    """
    return LogContext(**kwargs)
