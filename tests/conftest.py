"""
简化的测试配置
"""

from unittest.mock import Mock

import pytest


@pytest.fixture
def mock_request():
    """模拟FastAPI请求"""
    request = Mock()
    request.state = Mock()
    request.state.user_id = "test-user-123"
    return request


@pytest.fixture
def sample_file():
    """模拟文件"""
    file = Mock()
    file.filename = "test.txt"
    file.content_type = "text/plain"
    return file
