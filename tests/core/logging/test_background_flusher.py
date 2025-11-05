"""
LogBackgroundFlusher 单元测试

测试范围：
1. 启动和停止
2. 批量从Redis读取
3. 批量写入PostgreSQL
4. 失败重试
5. 优雅关闭
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from unifiles.core.logging.background_flusher import (
    LogBackgroundFlusher,
    get_log_flusher,
    start_log_flusher,
    stop_log_flusher,
)


@pytest.fixture
def mock_pool_manager():
    """模拟连接池管理器"""
    with patch('unifiles.core.logging.background_flusher.get_pool_manager') as mock:
        manager = AsyncMock()
        pool = AsyncMock()
        conn = AsyncMock()

        # 设置连接池
        pool.acquire.return_value.__aenter__.return_value = conn
        pool.acquire.return_value.__aexit__.return_value = None
        manager.pg_pool = pool

        mock.return_value = manager
        yield conn


@pytest.fixture
def mock_queue_service():
    """模拟队列服务"""
    with patch('unifiles.core.logging.background_flusher.get_queue_service') as mock:
        service = AsyncMock()
        mock.return_value = service
        yield service


class TestLogBackgroundFlusher:
    """LogBackgroundFlusher测试套件"""

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        """测试启动和停止"""
        flusher = LogBackgroundFlusher(batch_size=10, flush_interval=1.0)

        # 启动
        await flusher.start()
        assert flusher._running is True
        assert flusher._task is not None

        # 短暂等待
        await asyncio.sleep(0.1)

        # 停止
        await flusher.stop()
        assert flusher._running is False

    @pytest.mark.asyncio
    async def test_dequeue_batch(self, mock_queue_service):
        """测试批量从队列读取"""
        flusher = LogBackgroundFlusher(batch_size=5)

        # 模拟队列返回日志
        logs = [
            {"level": "INFO", "message": f"Log {i}"}
            for i in range(5)
        ]

        mock_queue_service.dequeue.side_effect = logs + [None]

        # 读取批次
        batch = await flusher._dequeue_batch(mock_queue_service)

        assert len(batch) == 5
        assert batch[0]['message'] == 'Log 0'

    @pytest.mark.asyncio
    async def test_batch_insert(self, mock_pool_manager):
        """测试批量插入数据库"""
        flusher = LogBackgroundFlusher()

        # 模拟日志批次
        batch = [
            {
                'timestamp': '2025-10-21T10:00:00',
                'level': 'INFO',
                'service_layer': 'app',
                'service_name': 'test_module',
                'message': f'Test log {i}',
                'trace_id': f'trace_{i}',
                'span_id': f'span_{i}',
                'user_id': f'user_{i}',
            }
            for i in range(10)
        ]

        # 执行批量插入
        await flusher._batch_insert(mock_pool_manager, batch)

        # 验证executemany被调用
        assert mock_pool_manager.executemany.called
        call_args = mock_pool_manager.executemany.call_args

        # 验证SQL语句
        sql = call_args.args[0]
        assert 'INSERT INTO unifiles.unified_logs' in sql

        # 验证记录数
        records = call_args.args[1]
        assert len(records) == 10

    @pytest.mark.asyncio
    async def test_flush_batch(self, mock_pool_manager, mock_queue_service):
        """测试批量刷新"""
        flusher = LogBackgroundFlusher()

        # 添加日志到批次
        flusher.batch = [
            {
                'timestamp': '2025-10-21T10:00:00',
                'level': 'INFO',
                'service_layer': 'app',
                'service_name': 'test_module',
                'message': 'Test log',
            }
        ]

        # 刷新批次
        await flusher._flush_batch()

        # 验证批次被清空
        assert len(flusher.batch) == 0

        # 验证数据库写入被调用
        assert mock_pool_manager.executemany.called

    @pytest.mark.asyncio
    async def test_flush_on_batch_size_threshold(self, mock_pool_manager, mock_queue_service):
        """测试达到批量大小时自动刷新"""
        flusher = LogBackgroundFlusher(batch_size=5, flush_interval=100.0)

        # 模拟队列返回日志
        logs = [
            {"timestamp": "2025-10-21T10:00:00", "level": "INFO", "message": f"Log {i}"}
            for i in range(5)
        ]
        mock_queue_service.dequeue.side_effect = logs + [None] * 100

        # 启动刷新器
        await flusher.start()

        # 等待批次被刷新
        await asyncio.sleep(2)

        # 停止
        await flusher.stop()

        # 验证数据库写入被调用
        assert mock_pool_manager.executemany.called

    @pytest.mark.asyncio
    async def test_flush_on_time_interval(self, mock_pool_manager, mock_queue_service):
        """测试达到时间间隔时自动刷新"""
        flusher = LogBackgroundFlusher(batch_size=100, flush_interval=1.0)

        # 模拟队列返回少量日志
        mock_queue_service.dequeue.side_effect = [
            {"timestamp": "2025-10-21T10:00:00", "level": "INFO", "message": "Log 1"}
        ] + [None] * 100

        # 启动刷新器
        await flusher.start()

        # 等待时间间隔
        await asyncio.sleep(2)

        # 停止
        await flusher.stop()

        # 验证数据库写入被调用（即使批次未满）
        assert mock_pool_manager.executemany.called

    @pytest.mark.asyncio
    async def test_flush_remaining_on_stop(self, mock_pool_manager, mock_queue_service):
        """测试停止时刷新剩余日志"""
        flusher = LogBackgroundFlusher()

        # 手动添加日志到批次
        flusher.batch = [
            {
                'timestamp': '2025-10-21T10:00:00',
                'level': 'INFO',
                'service_layer': 'app',
                'service_name': 'test_module',
                'message': 'Remaining log',
            }
        ]

        # 启动并立即停止
        await flusher.start()
        await asyncio.sleep(0.1)
        await flusher.stop()

        # 验证剩余日志被刷新
        assert mock_pool_manager.executemany.called
        assert len(flusher.batch) == 0

    @pytest.mark.asyncio
    async def test_retry_on_flush_failure(self, mock_pool_manager, mock_queue_service):
        """测试刷新失败时重试"""
        flusher = LogBackgroundFlusher()

        # 模拟数据库写入失败
        mock_pool_manager.executemany.side_effect = Exception("Database connection failed")

        # 添加日志到批次
        flusher.batch = [
            {
                'timestamp': '2025-10-21T10:00:00',
                'level': 'INFO',
                'service_layer': 'app',
                'service_name': 'test_module',
                'message': 'Test log',
            }
        ]

        # 尝试刷新
        await flusher._flush_batch()

        # 验证重新入队被尝试
        assert mock_queue_service.enqueue.called

    @pytest.mark.asyncio
    async def test_context_extraction(self, mock_pool_manager):
        """测试context字段提取"""
        flusher = LogBackgroundFlusher()

        # 模拟包含额外字段的日志
        batch = [
            {
                'timestamp': '2025-10-21T10:00:00',
                'level': 'INFO',
                'service_layer': 'app',
                'service_name': 'test_module',
                'message': 'Test log',
                'trace_id': 'trace_123',
                'user_id': 'user_456',  # 应该进入context
                'file_id': 'file_789',  # 应该进入context
                'custom_field': 'value',  # 应该进入context
            }
        ]

        # 执行批量插入
        await flusher._batch_insert(mock_pool_manager, batch)

        # 获取插入的记录
        records = mock_pool_manager.executemany.call_args.args[1]
        context_json = records[0][5]  # context字段在第6个位置

        import json
        context = json.loads(context_json)

        # 验证额外字段进入context
        assert 'user_id' in context
        assert context['user_id'] == 'user_456'
        assert 'file_id' in context
        assert 'custom_field' in context

    @pytest.mark.asyncio
    async def test_global_singleton(self):
        """测试全局单例"""
        flusher1 = await get_log_flusher()
        flusher2 = await get_log_flusher()

        # 验证是同一个实例
        assert flusher1 is flusher2

    @pytest.mark.asyncio
    async def test_start_stop_helpers(self):
        """测试启动/停止辅助函数"""
        # 启动全局刷新器
        await start_log_flusher()

        flusher = await get_log_flusher()
        assert flusher._running is True

        # 停止全局刷新器
        await stop_log_flusher()
        assert flusher._running is False

    @pytest.mark.asyncio
    async def test_double_start_warning(self):
        """测试重复启动警告"""
        flusher = LogBackgroundFlusher()

        await flusher.start()

        # 重复启动应该不报错
        await flusher.start()

        assert flusher._running is True

        await flusher.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        """测试未启动时停止"""
        flusher = LogBackgroundFlusher()

        # 未启动时停止不应报错
        await flusher.stop()

        assert flusher._running is False

    @pytest.mark.asyncio
    async def test_concurrent_flush(self, mock_pool_manager, mock_queue_service):
        """测试并发刷新"""
        flusher = LogBackgroundFlusher(batch_size=10, flush_interval=0.5)

        # 模拟大量日志
        logs = [
            {"timestamp": "2025-10-21T10:00:00", "level": "INFO", "message": f"Log {i}"}
            for i in range(50)
        ]
        mock_queue_service.dequeue.side_effect = logs + [None] * 100

        # 启动刷新器
        await flusher.start()

        # 等待多次刷新
        await asyncio.sleep(2)

        # 停止
        await flusher.stop()

        # 验证多次数据库写入
        assert mock_pool_manager.executemany.call_count >= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
