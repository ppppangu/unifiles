"""
日志查询API 单元测试

测试范围：
1. 基础查询（按时间、层次、级别）
2. trace_id查询
3. 业务字段查询
4. 全文搜索
5. 统计信息
6. 服务健康状态
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from unifiles.app.main import app


@pytest.fixture
def mock_pool_manager():
    """模拟连接池管理器"""
    with patch('unifiles.app.routers.logs.get_pool_manager') as mock:
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
def client():
    """测试客户端"""
    return TestClient(app)


class TestLogsAPI:
    """日志查询API测试套件"""

    def test_query_logs_basic(self, client, mock_pool_manager):
        """测试基础查询"""
        # 模拟数据库返回
        mock_pool_manager.fetch.return_value = [
            {
                'id': 1,
                'timestamp': datetime.now(),
                'service_layer': 'app',
                'service_name': 'test_module',
                'level': 'INFO',
                'message': 'Test log',
                'context': {},
                'trace_id': 'trace_123',
                'span_id': 'span_456',
                'exception_type': None,
                'module_name': 'test',
                'function_name': 'test_func',
            }
        ]
        mock_pool_manager.fetchval.return_value = 1

        response = client.get("/api/v1/logs?limit=10")

        assert response.status_code == 200
        data = response.json()

        assert data['success'] is True
        assert data['total'] == 1
        assert len(data['logs']) == 1
        assert data['logs'][0]['level'] == 'INFO'

    def test_query_logs_by_time_range(self, client, mock_pool_manager):
        """测试按时间范围查询"""
        mock_pool_manager.fetch.return_value = []
        mock_pool_manager.fetchval.return_value = 0

        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now()

        response = client.get(
            f"/api/v1/logs?start_time={start_time.isoformat()}&end_time={end_time.isoformat()}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_query_logs_by_last_hours(self, client, mock_pool_manager):
        """测试查询最近N小时"""
        mock_pool_manager.fetch.return_value = []
        mock_pool_manager.fetchval.return_value = 0

        response = client.get("/api/v1/logs?last_hours=24&limit=100")

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_query_logs_by_service_layer(self, client, mock_pool_manager):
        """测试按服务层次查询"""
        mock_pool_manager.fetch.return_value = []
        mock_pool_manager.fetchval.return_value = 0

        response = client.get("/api/v1/logs?service_layer=app")

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_query_logs_by_level(self, client, mock_pool_manager):
        """测试按级别查询"""
        mock_pool_manager.fetch.return_value = []
        mock_pool_manager.fetchval.return_value = 0

        response = client.get("/api/v1/logs?level=ERROR")

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_query_logs_by_user_id(self, client, mock_pool_manager):
        """测试按用户ID查询"""
        mock_pool_manager.fetch.return_value = []
        mock_pool_manager.fetchval.return_value = 0

        response = client.get("/api/v1/logs?user_id=user_123")

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_query_logs_by_file_id(self, client, mock_pool_manager):
        """测试按文件ID查询"""
        mock_pool_manager.fetch.return_value = []
        mock_pool_manager.fetchval.return_value = 0

        response = client.get("/api/v1/logs?file_id=file_456")

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_query_logs_by_search(self, client, mock_pool_manager):
        """测试全文搜索"""
        mock_pool_manager.fetch.return_value = []
        mock_pool_manager.fetchval.return_value = 0

        response = client.get("/api/v1/logs?search=connection failed")

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_query_logs_pagination(self, client, mock_pool_manager):
        """测试分页查询"""
        mock_pool_manager.fetch.return_value = []
        mock_pool_manager.fetchval.return_value = 100

        response = client.get("/api/v1/logs?limit=10&offset=20")

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['total'] == 100

    def test_query_logs_combined_filters(self, client, mock_pool_manager):
        """测试组合过滤条件"""
        mock_pool_manager.fetch.return_value = []
        mock_pool_manager.fetchval.return_value = 0

        response = client.get(
            "/api/v1/logs?service_layer=app&level=ERROR&user_id=user_123&last_hours=1"
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_query_by_trace_id_success(self, client, mock_pool_manager):
        """测试通过trace_id查询成功"""
        # 模拟数据库返回
        mock_pool_manager.fetch.return_value = [
            {
                'log_id': 1,
                'timestamp': datetime.now(),
                'service_layer': 'app',
                'service_name': 'test_module',
                'level': 'INFO',
                'message': 'Test log',
                'context': {},
                'span_id': 'span_456',
                'exception_type': None,
                'module_name': 'test',
                'function_name': 'test_func',
                'line_number': 10,
            }
        ]

        response = client.get("/api/v1/logs/trace/trace_123")

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert len(data['logs']) == 1

    def test_query_by_trace_id_not_found(self, client, mock_pool_manager):
        """测试trace_id不存在"""
        mock_pool_manager.fetch.return_value = []

        response = client.get("/api/v1/logs/trace/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert 'detail' in data

    def test_get_log_stats(self, client, mock_pool_manager):
        """测试获取统计信息"""
        # 模拟数据库返回
        mock_pool_manager.fetchval.return_value = {
            'time_range': {
                'from': '2025-10-21T00:00:00',
                'to': '2025-10-21T23:59:59'
            },
            'total_logs': 1000,
            'by_level': {
                'DEBUG': 100,
                'INFO': 500,
                'WARNING': 200,
                'ERROR': 180,
                'CRITICAL': 20
            },
            'by_service_layer': {
                'app': 400,
                'worker': 300,
                'core': 300
            },
            'error_rate_percent': 20.0,
            'trace_coverage_percent': 95.0,
            'top_errors': [
                {
                    'exception_type': 'ValueError',
                    'count': 50,
                    'last_occurrence': '2025-10-21T23:00:00'
                }
            ]
        }

        response = client.get("/api/v1/logs/stats?since_hours=24")

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'stats' in data
        assert data['stats']['total_logs'] == 1000
        assert data['stats']['error_rate_percent'] == 20.0

    def test_get_service_health(self, client, mock_pool_manager):
        """测试获取服务健康状态"""
        # 模拟数据库返回
        mock_pool_manager.fetch.return_value = [
            {
                'service_layer': 'app',
                'service_name': 'unifiles-api',
                'total_logs': 1000,
                'error_count': 50,
                'critical_count': 5,
                'warning_count': 100,
                'error_rate_percent': 5.5,
                'last_activity': datetime.now(),
            },
            {
                'service_layer': 'worker',
                'service_name': 'FileUploadWorker',
                'total_logs': 500,
                'error_count': 10,
                'critical_count': 0,
                'warning_count': 20,
                'error_rate_percent': 2.0,
                'last_activity': datetime.now(),
            }
        ]

        response = client.get("/api/v1/logs/health")

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert len(data['services']) == 2
        assert data['services'][0]['service_layer'] == 'app'
        assert data['services'][0]['error_rate_percent'] == 5.5

    def test_query_logs_invalid_service_layer(self, client):
        """测试无效的service_layer"""
        response = client.get("/api/v1/logs?service_layer=invalid")

        # FastAPI应该返回422验证错误
        assert response.status_code == 422

    def test_query_logs_invalid_pagination(self, client):
        """测试无效的分页参数"""
        # limit超过最大值
        response = client.get("/api/v1/logs?limit=2000")
        assert response.status_code == 422

        # offset为负数
        response = client.get("/api/v1/logs?offset=-1")
        assert response.status_code == 422

    def test_query_logs_performance(self, client, mock_pool_manager):
        """测试查询性能"""
        import time

        mock_pool_manager.fetch.return_value = []
        mock_pool_manager.fetchval.return_value = 0

        start = time.time()
        response = client.get("/api/v1/logs?limit=100")
        elapsed = (time.time() - start) * 1000

        assert response.status_code == 200
        data = response.json()

        # 验证query_time_ms字段存在
        assert 'query_time_ms' in data
        assert data['query_time_ms'] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
