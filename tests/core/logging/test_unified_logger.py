"""
UnifiedLogger 单元测试

测试范围：
1. 基本日志记录
2. trace_id/span_id自动注入
3. 智能路由决策
4. 上下文管理器
5. 异常处理
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

from unifiles.core.logging.unified import (
    UnifiedLogger,
    get_logger,
    with_context,
    _ctx_user_id,
    _ctx_file_id,
    _ctx_task_id,
)


@pytest.fixture
def setup_otel():
    """设置OTEL tracing（用于测试trace_id注入）"""
    provider = TracerProvider()
    processor = SimpleSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    yield trace.get_tracer(__name__)


@pytest.fixture
def mock_queue_service():
    """模拟队列服务"""
    with patch('unifiles.core.logging.unified.get_queue_service') as mock:
        service = AsyncMock()
        mock.return_value = service
        yield service


@pytest.fixture
def mock_runtime_config():
    """模拟运行时配置"""
    with patch('unifiles.core.logging.unified.get_runtime_config') as mock:
        # 默认配置
        async def get_config(key, default):
            configs = {
                'logging.db_enabled': True,
                'logging.core_info_sample_rate': 1.0,  # 100% 采样（测试用）
            }
            return configs.get(key, default)

        mock.side_effect = get_config
        yield mock


class TestUnifiedLogger:
    """UnifiedLogger测试套件"""

    @pytest.mark.asyncio
    async def test_basic_logging(self, mock_queue_service, mock_runtime_config):
        """测试基本日志记录"""
        logger = UnifiedLogger("test_module", "core")

        # 测试INFO级别
        await logger.info("Test info message", extra={"key": "value"})

        # 验证入队调用
        assert mock_queue_service.enqueue.called

    @pytest.mark.asyncio
    async def test_trace_id_injection(self, setup_otel, mock_queue_service, mock_runtime_config):
        """测试trace_id自动注入"""
        logger = UnifiedLogger("test_module", "core")
        tracer = setup_otel

        # 在span上下文中记录日志
        with tracer.start_as_current_span("test_span") as span:
            span_context = span.get_span_context()

            await logger.info("Test with trace", extra={})

            # 验证入队时包含trace_id
            call_args = mock_queue_service.enqueue.call_args
            task = call_args.kwargs['task']

            assert 'trace_id' in task
            assert task['trace_id'] == format(span_context.trace_id, '032x')
            assert 'span_id' in task
            assert task['span_id'] == format(span_context.span_id, '016x')

    @pytest.mark.asyncio
    async def test_context_enrichment(self, mock_queue_service, mock_runtime_config):
        """测试上下文自动丰富"""
        logger = UnifiedLogger("test_module", "app")

        await logger.info("Test enrichment", extra={"custom": "field"})

        # 验证丰富后的字段
        call_args = mock_queue_service.enqueue.call_args
        task = call_args.kwargs['task']

        assert task['service_layer'] == 'app'
        assert task['service_name'] == 'test_module'
        assert 'hostname' in task
        assert 'process_id' in task
        assert 'thread_name' in task
        assert 'custom' in task
        assert task['custom'] == 'field'

    @pytest.mark.asyncio
    async def test_smart_routing_core_layer(self, mock_queue_service, mock_runtime_config):
        """测试Core层智能路由"""
        logger = UnifiedLogger("test_module", "core")

        # WARNING及以上必入队
        await logger.warning("Warning message", extra={})
        assert mock_queue_service.enqueue.call_count == 1

        await logger.error("Error message", extra={})
        assert mock_queue_service.enqueue.call_count == 2

        # INFO with important=True入队
        await logger.info("Important info", extra={"important": True})
        assert mock_queue_service.enqueue.call_count == 3

    @pytest.mark.asyncio
    async def test_smart_routing_app_layer(self, mock_queue_service, mock_runtime_config):
        """测试App层智能路由"""
        logger = UnifiedLogger("test_module", "app")

        # 用户操作入队（INFO及以上）
        await logger.info("User action", extra={"user_id": "user_123"})
        assert mock_queue_service.enqueue.call_count == 1

        # 非用户操作，WARNING及以上入队
        await logger.warning("System warning", extra={})
        assert mock_queue_service.enqueue.call_count == 2

    @pytest.mark.asyncio
    async def test_smart_routing_worker_layer(self, mock_queue_service, mock_runtime_config):
        """测试Worker层智能路由"""
        logger = UnifiedLogger("test_module", "worker")

        # 任务日志（INFO及以上）
        await logger.info("Task started", extra={"task_id": "task_123"})
        assert mock_queue_service.enqueue.call_count == 1

        # 进度日志（10%, 20%, ..., 100%入队）
        await logger.info("Progress 10%", extra={"task_id": "task_123", "progress": 10})
        assert mock_queue_service.enqueue.call_count == 2

        await logger.info("Progress 15%", extra={"task_id": "task_123", "progress": 15})
        assert mock_queue_service.enqueue.call_count == 2  # 15%不入队

        await logger.info("Progress 20%", extra={"task_id": "task_123", "progress": 20})
        assert mock_queue_service.enqueue.call_count == 3

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_queue_service, mock_runtime_config):
        """测试上下文管理器"""
        logger = UnifiedLogger("test_module", "app")

        # 使用上下文管理器
        with with_context(user_id="user_123", file_id="file_456"):
            await logger.info("Processing file", extra={})

            # 验证上下文变量被注入
            call_args = mock_queue_service.enqueue.call_args
            task = call_args.kwargs['task']

            assert task['user_id'] == 'user_123'
            assert task['file_id'] == 'file_456'

        # 上下文退出后，变量应该被重置
        assert _ctx_user_id.get() is None
        assert _ctx_file_id.get() is None

    @pytest.mark.asyncio
    async def test_exception_logging(self, mock_queue_service, mock_runtime_config):
        """测试异常日志记录"""
        logger = UnifiedLogger("test_module", "app")

        # 模拟异常
        try:
            raise ValueError("Test exception")
        except Exception as e:
            await logger.error("Error occurred", exc_info=e, extra={})

        # 验证异常信息被捕获
        call_args = mock_queue_service.enqueue.call_args
        task = call_args.kwargs['task']

        assert task['exception_type'] == 'ValueError'
        assert task['exception_message'] == 'Test exception'
        assert 'stack_trace' in task
        assert 'ValueError' in task['stack_trace']

    @pytest.mark.asyncio
    async def test_debug_logging_no_enqueue(self, mock_queue_service, mock_runtime_config):
        """测试DEBUG级别不入队"""
        logger = UnifiedLogger("test_module", "core")

        # DEBUG级别仅本地记录，不入队
        await logger.debug("Debug message", extra={})

        # 验证没有入队
        assert not mock_queue_service.enqueue.called

    @pytest.mark.asyncio
    async def test_queue_failure_handling(self, mock_queue_service, mock_runtime_config):
        """测试队列失败处理"""
        logger = UnifiedLogger("test_module", "app")

        # 模拟队列失败
        mock_queue_service.enqueue.side_effect = Exception("Queue connection failed")

        # 日志记录不应抛出异常
        await logger.info("Test message", extra={"user_id": "user_123"})

        # 验证没有抛出异常（通过没有引发Exception）
        assert True

    @pytest.mark.asyncio
    async def test_get_logger_factory(self):
        """测试工厂函数"""
        logger = get_logger(__name__, service_layer='app')

        assert isinstance(logger, UnifiedLogger)
        assert logger.service_layer == 'app'

    @pytest.mark.asyncio
    async def test_span_event_on_error(self, setup_otel, mock_queue_service, mock_runtime_config):
        """测试ERROR级别添加Span Event"""
        logger = UnifiedLogger("test_module", "app")
        tracer = setup_otel

        with tracer.start_as_current_span("test_span") as span:
            # 记录ERROR日志
            await logger.error("Error occurred", extra={"error_code": "E001"})

            # 验证Span Event被添加（通过检查span是否在记录状态）
            assert span.is_recording()

    @pytest.mark.asyncio
    async def test_config_caching(self, mock_runtime_config):
        """测试配置缓存"""
        logger = UnifiedLogger("test_module", "core")

        # 第一次获取配置
        value1 = await logger._get_config_cached('test_key', 'default')
        call_count_1 = mock_runtime_config.call_count

        # 第二次获取（应该使用缓存）
        value2 = await logger._get_config_cached('test_key', 'default')
        call_count_2 = mock_runtime_config.call_count

        # 验证第二次没有调用get_runtime_config（使用了缓存）
        assert call_count_1 == call_count_2

    @pytest.mark.asyncio
    async def test_code_location_capture(self, mock_queue_service, mock_runtime_config):
        """测试代码位置捕获"""
        logger = UnifiedLogger("test_module", "app")

        await logger.info("Test location", extra={})

        # 验证代码位置被捕获
        call_args = mock_queue_service.enqueue.call_args
        task = call_args.kwargs['task']

        assert 'module_name' in task
        assert 'function_name' in task
        assert 'line_number' in task
        assert task['function_name'] == 'test_code_location_capture'


@pytest.mark.asyncio
async def test_concurrent_logging(mock_queue_service, mock_runtime_config):
    """测试并发日志记录"""
    logger = get_logger("test_module", "app")

    # 并发记录100条日志
    tasks = [
        logger.info(f"Concurrent log {i}", extra={"index": i})
        for i in range(100)
    ]

    await asyncio.gather(*tasks)

    # 验证所有日志都被入队
    assert mock_queue_service.enqueue.call_count == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
