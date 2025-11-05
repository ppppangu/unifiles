"""
存储系统相关类型

包含存储提供商类型、连接配置、存储配置等。

参考 FastAPI 的 security 子包设计。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Literal, Optional, Union


# ===== Enums =====

class ProviderType(str, Enum):
    """存储提供商类型"""

    LOCAL = "local"
    MINIO = "minio"
    S3 = "s3"
    AZURE = "azure"
    GCS = "gcs"


class ConfigSource(str, Enum):
    """配置来源"""

    ENV = "env"
    MANUAL = "manual"


# ===== Connection Configurations =====

@dataclass
class BaseConnection(ABC):
    """存储连接配置基类"""

    provider: ProviderType

    @abstractmethod
    def validate_connection(self) -> None:
        """验证连接配置"""
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseConnection':
        """从字典创建实例"""
        pass


@dataclass
class LocalConnection(BaseConnection):
    """本地文件系统连接"""

    provider: Literal[ProviderType.LOCAL] = ProviderType.LOCAL
    base_path: str = field(default="")
    create_if_missing: bool = field(default=True)

    def validate_connection(self) -> None:
        if not self.base_path:
            raise ValueError("Local storage requires base_path")

        from pathlib import Path
        path = Path(self.base_path)
        if not path.is_absolute():
            raise ValueError("Local storage base_path must be absolute")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider.value,
            "base_path": self.base_path,
            "create_if_missing": self.create_if_missing
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LocalConnection':
        return cls(
            base_path=data.get("base_path", ""),
            create_if_missing=data.get("create_if_missing", True)
        )


@dataclass
class MinIOConnection(BaseConnection):
    """MinIO 对象存储连接"""

    provider: Literal[ProviderType.MINIO] = ProviderType.MINIO
    endpoint: str = field(default="")
    access_key: str = field(default="")
    secret_key: str = field(default="")
    bucket_name: str = field(default="")
    region: str = field(default="us-east-1")
    secure: bool = field(default=True)

    def validate_connection(self) -> None:
        required_fields = ["endpoint", "access_key", "secret_key", "bucket_name"]
        missing_fields = []

        for field_name in required_fields:
            if not getattr(self, field_name):
                missing_fields.append(field_name)

        if missing_fields:
            raise ValueError(f"MinIO connection missing required fields: {', '.join(missing_fields)}")

        if self.endpoint and '://' in self.endpoint:
            from urllib.parse import urlparse
            parsed = urlparse(self.endpoint)
            if parsed.netloc:
                self.endpoint = parsed.netloc

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider.value,
            "endpoint": self.endpoint,
            "access_key": self.access_key,
            "secret_key": self.secret_key,
            "bucket_name": self.bucket_name,
            "region": self.region,
            "secure": self.secure
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MinIOConnection':
        return cls(
            endpoint=data.get("endpoint", ""),
            access_key=data.get("access_key", ""),
            secret_key=data.get("secret_key", ""),
            bucket_name=data.get("bucket_name", ""),
            region=data.get("region", "us-east-1"),
            secure=data.get("secure", True)
        )


@dataclass
class S3Connection(BaseConnection):
    """AWS S3 存储连接"""

    provider: Literal[ProviderType.S3] = ProviderType.S3
    access_key: str = field(default="")
    secret_key: str = field(default="")
    bucket_name: str = field(default="")
    region: str = field(default="us-east-1")
    endpoint: Optional[str] = field(default=None)

    def validate_connection(self) -> None:
        required_fields = ["access_key", "secret_key", "bucket_name", "region"]
        missing_fields = []

        for field_name in required_fields:
            if not getattr(self, field_name):
                missing_fields.append(field_name)

        if missing_fields:
            raise ValueError(f"S3 connection missing required fields: {', '.join(missing_fields)}")

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "provider": self.provider.value,
            "access_key": self.access_key,
            "secret_key": self.secret_key,
            "bucket_name": self.bucket_name,
            "region": self.region
        }
        if self.endpoint:
            result["endpoint"] = self.endpoint
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'S3Connection':
        return cls(
            access_key=data.get("access_key", ""),
            secret_key=data.get("secret_key", ""),
            bucket_name=data.get("bucket_name", ""),
            region=data.get("region", "us-east-1"),
            endpoint=data.get("endpoint")
        )


@dataclass
class AzureConnection(BaseConnection):
    """Azure Blob Storage 连接"""

    provider: Literal[ProviderType.AZURE] = ProviderType.AZURE
    account_name: str = field(default="")
    container_name: str = field(default="")
    account_key: Optional[str] = field(default=None)
    sas_token: Optional[str] = field(default=None)

    def validate_connection(self) -> None:
        if not self.account_name:
            raise ValueError("Azure connection requires account_name")

        if not self.container_name:
            raise ValueError("Azure connection requires container_name")

        if not self.account_key and not self.sas_token:
            raise ValueError("Azure connection requires either account_key or sas_token")

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "provider": self.provider.value,
            "account_name": self.account_name,
            "container_name": self.container_name
        }
        if self.account_key:
            result["account_key"] = self.account_key
        if self.sas_token:
            result["sas_token"] = self.sas_token
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AzureConnection':
        return cls(
            account_name=data.get("account_name", ""),
            container_name=data.get("container_name", ""),
            account_key=data.get("account_key"),
            sas_token=data.get("sas_token")
        )


@dataclass
class GCSConnection(BaseConnection):
    """Google Cloud Storage 连接"""

    provider: Literal[ProviderType.GCS] = ProviderType.GCS
    bucket_name: str = field(default="")
    credentials_json_path: Optional[str] = field(default=None)
    service_account_key_json: Optional[str] = field(default=None)
    project_id: Optional[str] = field(default=None)

    def validate_connection(self) -> None:
        if not self.bucket_name:
            raise ValueError("GCS connection requires bucket_name")

        if not self.credentials_json_path and not self.service_account_key_json:
            raise ValueError("GCS connection requires either credentials_json_path or service_account_key_json")

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "provider": self.provider.value,
            "bucket_name": self.bucket_name
        }
        if self.credentials_json_path:
            result["credentials_json_path"] = self.credentials_json_path
        if self.service_account_key_json:
            result["service_account_key_json"] = self.service_account_key_json
        if self.project_id:
            result["project_id"] = self.project_id
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GCSConnection':
        return cls(
            bucket_name=data.get("bucket_name", ""),
            credentials_json_path=data.get("credentials_json_path"),
            service_account_key_json=data.get("service_account_key_json"),
            project_id=data.get("project_id")
        )


# ===== Union Types =====

ConnectionConfig = Union[
    LocalConnection,
    MinIOConnection,
    S3Connection,
    AzureConnection,
    GCSConnection
]


# ===== Storage Configuration =====

@dataclass
class StorageConfig:
    """存储配置"""

    id: str
    name: str
    connection: ConnectionConfig
    is_active: bool = True
    config_source: ConfigSource = ConfigSource.MANUAL
    public_url_prefix: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        self.validate()

    def validate(self) -> None:
        if not self.id:
            raise ValueError("Storage config ID is required")

        if not self.name:
            raise ValueError("Storage config name is required")

        if self.connection:
            self.connection.validate_connection()

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'id': self.id,
            'name': self.name,
            'is_active': self.is_active,
            'config_source': self.config_source.value,
            'public_url_prefix': self.public_url_prefix,
            'metadata': self.metadata or {}
        }

        if self.connection:
            result['connection'] = self.connection.to_dict()

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StorageConfig':
        config_source = ConfigSource(data.get('config_source', 'manual'))

        if 'connection' not in data:
            raise ValueError("StorageConfig requires 'connection' field")

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
        if self.public_url_prefix:
            bucket_name = ""
            if isinstance(self.connection, (MinIOConnection, S3Connection)):
                bucket_name = self.connection.bucket_name
            return f"{self.public_url_prefix.rstrip('/')}/{bucket_name}/{object_path}"

        # 使用connection配置作为兜底
        if isinstance(self.connection, MinIOConnection):
            protocol = "https" if self.connection.secure else "http"
            return f"{protocol}://{self.connection.endpoint}/{self.connection.bucket_name}/{object_path}"
        if isinstance(self.connection, S3Connection):
            endpoint = self.connection.endpoint or f"s3.{self.connection.region}.amazonaws.com"
            return f"https://{endpoint}/{self.connection.bucket_name}/{object_path}"
        raise ValueError("Cannot generate public URL for this storage type")


# ===== Factory Functions =====

def create_connection_from_dict(data: Dict[str, Any]) -> ConnectionConfig:
    """从字典创建连接配置实例"""

    provider_str = data.get("provider", "").lower()

    try:
        provider = ProviderType(provider_str)
    except ValueError:
        available_providers = ', '.join([p.value for p in ProviderType])
        raise ValueError(f"Unsupported provider: '{provider_str}'. Available: {available_providers}")

    connection_classes = {
        ProviderType.LOCAL: LocalConnection,
        ProviderType.MINIO: MinIOConnection,
        ProviderType.S3: S3Connection,
        ProviderType.AZURE: AzureConnection,
        ProviderType.GCS: GCSConnection
    }

    connection_class = connection_classes.get(provider)
    if not connection_class:
        raise ValueError(f"No connection class found for provider: {provider}")

    return connection_class.from_dict(data)
