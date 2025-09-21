"""
存储配置模型
定义存储配置的数据结构和验证逻辑
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
from enum import Enum


class StorageType(str, Enum):
    """存储类型枚举"""
    MINIO = "minio"
    LOCAL = "local"
    S3 = "s3"
    AZURE = "azure"


class ConfigSource(str, Enum):
    """配置来源枚举"""
    ENV = "env"
    MANUAL = "manual"
    DEFAULT = "default"


@dataclass
class StorageConfig:
    """存储配置数据类"""
    
    # 基础信息
    id: str
    type: StorageType
    name: str
    is_active: bool = True
    is_default: bool = False
    config_source: ConfigSource = ConfigSource.MANUAL
    
    # 连接信息
    endpoint: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    bucket_name: Optional[str] = None
    region: Optional[str] = None
    
    # URL配置
    public_url_prefix: Optional[str] = None
    base_path: Optional[str] = None
    
    # 安全配置
    secure: bool = True
    
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
        
        # 根据存储类型验证必需字段
        if self.type == StorageType.MINIO:
            self._validate_minio_config()
        elif self.type == StorageType.LOCAL:
            self._validate_local_config()
    
    def _validate_minio_config(self) -> None:
        """验证MinIO配置"""
        required_fields = ['endpoint', 'access_key', 'secret_key', 'bucket_name']
        missing_fields = []
        
        for field in required_fields:
            if not getattr(self, field):
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(f"MinIO config missing required fields: {', '.join(missing_fields)}")
        
        # 验证endpoint格式
        if self.endpoint and '://' in self.endpoint:
            # 移除协议前缀以获取纯endpoint
            self.endpoint = self.endpoint.split('://', 1)[1]

    def _validate_local_config(self) -> None:
        """验证本地存储配置"""
        if not self.base_path:
            raise ValueError("Local storage requires base_path")
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'type': self.type.value,
            'name': self.name,
            'is_active': self.is_active,
            'is_default': self.is_default,
            'config_source': self.config_source.value,
            'endpoint': self.endpoint,
            'access_key': self.access_key,
            'secret_key': self.secret_key,
            'bucket_name': self.bucket_name,
            'region': self.region,
            'public_url_prefix': self.public_url_prefix,
            'base_path': self.base_path,
            'secure': self.secure,
            'metadata': self.metadata or {}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StorageConfig':
        """从字典创建实例"""
        # 处理枚举类型
        storage_type = StorageType(data.get('type', 'minio'))
        config_source = ConfigSource(data.get('config_source', 'manual'))
        
        return cls(
            id=data['id'],
            type=storage_type,
            name=data['name'],
            is_active=data.get('is_active', True),
            is_default=data.get('is_default', False),
            config_source=config_source,
            endpoint=data.get('endpoint'),
            access_key=data.get('access_key') or data.get('access_key_id'),
            secret_key=data.get('secret_key') or data.get('secret_access_key'),
            bucket_name=data.get('bucket_name'),
            region=data.get('region'),
            public_url_prefix=data.get('public_url_prefix'),
            base_path=data.get('base_path'),
            secure=data.get('secure', True),
            metadata=data.get('metadata')
        )
    
    @classmethod
    def from_env_config(cls, env_config: Dict[str, Any], config_id: str = "default-minio") -> 'StorageConfig':
        """从环境配置创建实例"""
        return cls(
            id=config_id,
            type=StorageType.MINIO,
            name="MinIO Object Storage (from env)",
            is_active=True,
            is_default=True,
            config_source=ConfigSource.ENV,
            endpoint=env_config.get('endpoint') or env_config.get('address'),
            access_key=env_config.get('access_key'),
            secret_key=env_config.get('secret_key'),
            bucket_name=env_config.get('bucket_name', 'unifiles'),
            region=env_config.get('region', 'us-east-1'),
            public_url_prefix=env_config.get('public_url_prefix'),
            secure=env_config.get('secure', False)
        )
    
    def get_minio_client_config(self) -> Dict[str, Any]:
        """获取MinIO客户端配置"""
        if self.type != StorageType.MINIO:
            raise ValueError("Not a MinIO configuration")
        
        return {
            'endpoint': self.endpoint,
            'access_key': self.access_key,
            'secret_key': self.secret_key,
            'secure': self.secure,
            'region': self.region
        }
    
    def generate_public_url(self, object_path: str) -> str:
        """生成公网访问URL"""
        if self.public_url_prefix:
            return f"{self.public_url_prefix.rstrip('/')}/{self.bucket_name}/{object_path}"
        
        # 使用endpoint作为兜底
        protocol = "https" if self.secure else "http"
        return f"{protocol}://{self.endpoint}/{self.bucket_name}/{object_path}"