"""
存储配置模型
定义存储配置的数据结构和验证逻辑
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
from enum import Enum

from .connection_config import ConnectionConfig, create_connection_from_dict


class ConfigSource(str, Enum):
    """配置来源枚举"""
    ENV = "env"
    MANUAL = "manual"

@dataclass
class StorageConfig:
    """存储配置数据类"""
    
    # 基础信息
    id: str
    name: str
    connection: ConnectionConfig
    is_active: bool = True
    config_source: ConfigSource = ConfigSource.MANUAL
    
    # URL配置
    public_url_prefix: Optional[str] = None
    
    # 额外配置
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """初始化后验证"""
        self.validate()
    
    def validate(self) -> None:
        """验证配置"""
        if not self.id:
            raise ValueError("Storage config ID is required")
        
        if not self.name:
            raise ValueError("Storage config name is required")
        
        # 验证连接配置
        if self.connection:
            self.connection.validate_connection()
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            'id': self.id,
            'name': self.name,
            'is_active': self.is_active,
            'config_source': self.config_source.value,
            'public_url_prefix': self.public_url_prefix,
            'metadata': self.metadata or {}
        }
        
        # Add connection configuration
        if self.connection:
            result['connection'] = self.connection.to_dict()
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StorageConfig':
        """从字典创建实例（仅支持新格式）"""
        config_source = ConfigSource(data.get('config_source', 'manual'))
        
        # 只支持新格式 - connection 字段必须存在
        if 'connection' not in data:
            raise ValueError("StorageConfig requires 'connection' field. Legacy format not supported.")
        
        connection = create_connection_from_dict(data['connection'])
        
        return cls(
            id=data['id'],
            name=data['name'],
            connection=connection,
            is_active=data.get('is_active', True),
            config_source=config_source,
            public_url_prefix=data.get('public_url_prefix'),
            metadata=data.get('metadata')
        )
    
    @classmethod
    def from_env_config(cls, env_config: Dict[str, Any], config_id: str = "default-minio") -> 'StorageConfig':
        """从环境配置创建实例"""
        from .connection_config import MinIOConnection
        
        # Create MinIO connection from env config
        connection = MinIOConnection(
            endpoint=env_config.get('endpoint') or env_config.get('address', 'localhost:9000'),
            access_key=env_config.get('access_key', ''),
            secret_key=env_config.get('secret_key', ''),
            bucket_name=env_config.get('bucket_name', 'unifiles'),
            region=env_config.get('region', 'us-east-1'),
            secure=env_config.get('secure', False)
        )
        
        return cls(
            id=config_id,
            name="MinIO Object Storage (from env)",
            connection=connection,
            is_active=True,
            config_source=ConfigSource.ENV,
            public_url_prefix=env_config.get('public_url_prefix')
        )
    
    def get_minio_client_config(self) -> Dict[str, Any]:
        """获取MinIO客户端配置"""
        from .connection_config import MinIOConnection, ProviderType
        
        if not isinstance(self.connection, MinIOConnection):
            raise ValueError("Not a MinIO configuration")
        
        return {
            'endpoint': self.connection.endpoint,
            'access_key': self.connection.access_key,
            'secret_key': self.connection.secret_key,
            'secure': self.connection.secure,
            'region': self.connection.region
        }
    
    def generate_public_url(self, object_path: str) -> str:
        """生成公网访问URL"""
        from .connection_config import MinIOConnection, S3Connection, ProviderType
        
        if self.public_url_prefix:
            bucket_name = ""
            if isinstance(self.connection, (MinIOConnection, S3Connection)):
                bucket_name = self.connection.bucket_name
            return f"{self.public_url_prefix.rstrip('/')}/{bucket_name}/{object_path}"
        
        # 使用connection配置作为兜底
        if isinstance(self.connection, MinIOConnection):
            protocol = "https" if self.connection.secure else "http"
            return f"{protocol}://{self.connection.endpoint}/{self.connection.bucket_name}/{object_path}"
        elif isinstance(self.connection, S3Connection):
            endpoint = self.connection.endpoint or f"s3.{self.connection.region}.amazonaws.com"
            return f"https://{endpoint}/{self.connection.bucket_name}/{object_path}"
        else:
            raise ValueError("Cannot generate public URL for this storage type")