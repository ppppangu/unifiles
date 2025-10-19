"""
单元测试 - 干净的存储系统测试
测试新的存储配置架构（无遗留兼容性）
"""

import json

import pytest

from unifiles.core.config.models import (
    LocalConnection,
    MinIOConnection,
    ProviderType,
    StorageConfig,
    create_connection_from_dict,
)
from unifiles.core.storage.factory import StorageFactory


class TestConnectionModels:
    """测试连接模型"""

    def test_minio_connection_creation_and_validation(self):
        """测试MinIO连接创建和验证"""
        conn = MinIOConnection(
            endpoint="localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            bucket_name="test-bucket"
        )

        assert conn.provider == ProviderType.MINIO
        assert conn.endpoint == "localhost:9000"
        conn.validate_connection()  # 应该不抛异常

    def test_local_connection_creation_and_validation(self):
        """测试本地连接创建和验证"""
        conn = LocalConnection(base_path="/tmp/storage")

        assert conn.provider == ProviderType.LOCAL
        assert conn.base_path == "/tmp/storage"
        conn.validate_connection()  # 应该不抛异常

    def test_connection_factory(self):
        """测试连接工厂"""
        minio_data = {
            "provider": "minio",
            "endpoint": "localhost:9000",
            "access_key": "admin",
            "secret_key": "admin",
            "bucket_name": "test"
        }

        conn = create_connection_from_dict(minio_data)
        assert isinstance(conn, MinIOConnection)
        assert conn.endpoint == "localhost:9000"


class TestStorageConfig:
    """测试存储配置模型"""

    def test_storage_config_with_minio_connection(self):
        """测试带MinIO连接的存储配置"""
        connection = MinIOConnection(
            endpoint="localhost:9000",
            access_key="admin",
            secret_key="admin",
            bucket_name="test"
        )

        config = StorageConfig(
            id="test-minio",
            name="Test MinIO",
            connection=connection
        )

        assert config.id == "test-minio"
        assert isinstance(config.connection, MinIOConnection)
        config.validate()  # 应该不抛异常

    def test_storage_config_to_dict(self):
        """测试存储配置序列化"""
        connection = LocalConnection(base_path="/tmp/test")
        config = StorageConfig(
            id="test-local",
            name="Test Local",
            connection=connection
        )

        result = config.to_dict()

        assert result['id'] == 'test-local'
        assert result['connection']['provider'] == 'local'
        assert result['connection']['base_path'] == '/tmp/test'

    def test_storage_config_from_dict_new_format(self):
        """测试从新格式字典创建存储配置"""
        data = {
            'id': 'test-config',
            'name': 'Test Storage',
            'connection': {
                'provider': 'minio',
                'endpoint': 'localhost:9000',
                'access_key': 'admin',
                'secret_key': 'admin',
                'bucket_name': 'test'
            }
        }

        config = StorageConfig.from_dict(data)

        assert config.id == 'test-config'
        assert isinstance(config.connection, MinIOConnection)
        assert config.connection.endpoint == 'localhost:9000'

    def test_storage_config_from_dict_missing_connection(self):
        """测试缺少连接字段时的错误处理"""
        data = {
            'id': 'test-config',
            'name': 'Test Storage'
            # 缺少 connection 字段
        }

        with pytest.raises(ValueError, match="StorageConfig requires 'connection' field"):
            StorageConfig.from_dict(data)


class TestStorageFactory:
    """测试存储工厂"""

    def test_factory_only_accepts_storage_config(self):
        """测试工厂只接受StorageConfig对象"""
        config_dict = {'id': 'test'}

        with pytest.raises(ValueError, match="Factory only accepts StorageConfig objects"):
            StorageFactory.create_storage(config_dict)

    def test_factory_unsupported_provider(self):
        """测试不支持的提供商错误处理"""
        # 创建一个不支持的连接类型
        connection = LocalConnection(base_path="/tmp/test")
        config = StorageConfig(
            id="test-config",
            name="Test Storage",
            connection=connection
        )

        # LOCAL provider 不在当前的 _backends 中
        with pytest.raises(ValueError, match="Unsupported provider type"):
            StorageFactory.create_storage(config)


class TestDatabaseIntegration:
    """测试数据库集成"""

    @pytest.fixture
    def sample_db_config(self):
        """示例数据库配置"""
        return {
            'id': 'test-minio',
            'storage_name': 'Test MinIO Storage',
            'connection_config': json.dumps({
                'provider': 'minio',
                'endpoint': 'localhost:9000',
                'access_key': 'admin',
                'secret_key': 'admin',
                'bucket_name': 'test',
                'region': 'us-east-1',
                'secure': False
            }),
            'is_active': True,
            'config_source': 'manual',
            'public_url_prefix': 'https://cdn.example.com',
            'metadata': json.dumps({}),
            'created_at': '2023-01-01T00:00:00Z',
            'updated_at': '2023-01-01T00:00:00Z'
        }

    def test_storage_config_from_db_format(self, sample_db_config):
        """测试从数据库格式创建存储配置"""
        # 解析connection_config JSON
        connection_data = json.loads(sample_db_config['connection_config'])

        # 构建StorageConfig字典
        config_data = {
            'id': sample_db_config['id'],
            'name': sample_db_config['storage_name'],
            'connection': connection_data,
            'is_active': sample_db_config['is_active'],
            'config_source': sample_db_config['config_source'],
            'public_url_prefix': sample_db_config['public_url_prefix']
        }

        config = StorageConfig.from_dict(config_data)

        assert config.id == 'test-minio'
        assert isinstance(config.connection, MinIOConnection)
        assert config.connection.endpoint == 'localhost:9000'
        assert config.connection.secure is False


if __name__ == "__main__":
    pytest.main([__file__])
